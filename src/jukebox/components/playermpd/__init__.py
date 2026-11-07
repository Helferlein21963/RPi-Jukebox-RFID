# -*- coding: utf-8 -*-
"""
Package for interfacing with the MPD Music Player Daemon

Status information in three topics
1) Player Status: published only on change
  This is a subset of the MPD status (and not the full MPD status) ??
  - folder
  - song
  - volume (volume is published only via player status, and not separatly to avoid too many Threads)
  - ...
2) Elapsed time: published every 250 ms, unless constant
  - elapsed
3) Folder Config: published only on change
   This belongs to the folder being played
   Publish:
   - random, resume, single, loop
   On save store this information:
   Contains the information for resume functionality of each folder
   - random, resume, single, loop
   - if resume:
     - current song, elapsed
   - what is PLAYSTATUS for?
   When to save
   - on stop
   Angstsave:
   - on pause (only if box get turned off without proper shutdown - else stop gets implicitly called)
   - on status change of random, resume, single, loop (for resume omit current status if currently playing- this has now meaning)
   Load checks:
   - if resume, but no song, elapsed -> log error and start from the beginning

Status storing:
  - Folder config for each folder (see above)
  - Information to restart last folder playback, which is:
    - last_folder -> folder_on_close
    - song, elapsed
    - random, resume, single, loop
    - if resume is enabled, after start we need to set last_played_folder, such that card swipe is detected as second swipe?!
      on the other hand: if resume is enabled, this is also saved to folder.config -> and that is checked by play card

Internal status
  - last played folder: Needed to detect second swipe


Saving {'player_status': {'last_played_folder': 'TraumfaengerStarkeLieder', 'CURRENTSONGPOS': '0', 'CURRENTFILENAME': 'TraumfaengerStarkeLieder/01.mp3'},
'audio_folder_status':
{'TraumfaengerStarkeLieder': {'ELAPSED': '1.0', 'CURRENTFILENAME': 'TraumfaengerStarkeLieder/01.mp3', 'CURRENTSONGPOS': '0', 'PLAYSTATUS': 'stop', 'RESUME': 'OFF', 'SHUFFLE': 'OFF', 'LOOP': 'OFF', 'SINGLE': 'OFF'},
'Giraffenaffen': {'ELAPSED': '1.0', 'CURRENTFILENAME': 'TraumfaengerStarkeLieder/01.mp3', 'CURRENTSONGPOS': '0', 'PLAYSTATUS': 'play', 'RESUME': 'OFF', 'SHUFFLE': 'OFF', 'LOOP': 'OFF', 'SINGLE': 'OFF'}}}

References:
https://github.com/Mic92/python-mpd2
https://python-mpd2.readthedocs.io/en/latest/topics/commands.html
https://mpd.readthedocs.io/en/latest/protocol.html

sudo -u mpd speaker-test -t wav -c 2
"""  # noqa: E501
# Warum ist "Second Swipe" im Player und nicht im RFID Reader?
# Second swipe ist abhängig vom Player State - nicht vom RFID state.
# Beispiel: RFID triggered Folder1, Web App triggered Folder2, RFID Folder1:
# Dann muss das 2. Mal Folder1 auch als "first swipe" gewertet werden.
# Wenn der RFID das basierend auf IDs macht, kann der nicht  unterscheiden und glaubt es ist 2. Swipe.
# Beispiel 2: Jemand hat RFID Reader (oder 1x RFID und 1x Barcode Scanner oder so) angeschlossen. Liest zuerst Karte mit
# Reader 1 und dann mit Reader 2: Reader 2 weiß nicht, was bei Reader 1 passiert ist und denkt es ist 1. swipe.
# Beispiel 3: RFID trigered Folder1, Playlist läuft durch und hat schon gestoppt, dann wird die Karte wieder vorgehalten.
# Dann muss das als 1. Swipe gewertet werden
# Beispiel 4: RFID triggered "Folder1", dann wird Karte "Volume Up" aufgelegt, dann wieder Karte "Folder1": Auch das ist
# aus Sicht ders Playbacks 2nd Swipe
# 2nd Swipe ist keine im Reader festgelegte Funktion extra fur den Player.
#
# In der aktuellen Implementierung weiß der Player (der second "swipe" dekodiert) überhaupt nichts vom RFID.
# Im Prinzip gibt es zwei "Play" Funktionen: (1) play always from start und (2) play with toggle action.
# Die Web App ruft immer (1) auf und die RFID immer (2). Jetzt kann man sogar für einige Karten sagen
# immer (1) - also kein Second Swipe und für andere (2).
# Sollte der Reader das Swcond swipe dekodieren, muss aber der Reader den Status des Player kennen.
# Das ist allerdings ein Problem. In Version 2 ist das nicht aufgefallen,
# weil alles uber File I/Os lief - Thread safe ist das nicht!
#
# Beispiel: Second swipe bei anderen Funktionen, hier: WiFi on/off.
# Was die Karte Action tut ist ein Toggle. Der Toggle hängt vom Wifi State ab, den der RFID Kartenleser nicht kennt.
# Den kann der Leser auch nicht tracken. Der State kann ja auch über die Web App oder Kommandozeile geändert werden.
# Toggle (und 2nd Swipe generell) ist immer vom Status des Zielsystems abhängig und kann damit nur vom Zielsystem geändert
# werden. Bei Wifi also braucht man 3 Funktionen: on / off / toggle. Toggle ist dann first swipe / second swipe

import os
import mpd
import threading
import logging
import time
import functools
from typing import Optional
from slugify import slugify
import components.player
import jukebox.cfghandler
import jukebox.utils as utils
import jukebox.plugs as plugs
import jukebox.multitimer as multitimer
import jukebox.publishing as publishing
import jukebox.playlistgenerator as playlistgenerator
import misc

from jukebox.NvManager import nv_manager
from .playcontentcallback import PlayContentCallbacks, PlayCardState
from .coverart_cache_manager import CoverartCacheManager

logger = logging.getLogger('jb.PlayerMPD')
cfg = jukebox.cfghandler.get_handler('jukebox')

#: Remaining time [s] of the last song, below which a following stop counts as "playlist has played to its end"
PLAYLIST_END_MARGIN = 2.0


def _is_last_song_ending(status: dict) -> bool:
    """Return True if the MPD status shows the last song of the playlist within its final seconds"""
    try:
        return (int(status['song']) == int(status['playlistlength']) - 1
                and float(status['duration']) - float(status['elapsed']) < PLAYLIST_END_MARGIN)
    except (KeyError, ValueError):
        return False


class MpdLock:
    def __init__(self, client: mpd.MPDClient, host: str, port: int):
        self._lock = threading.RLock()
        self.client = client
        self.host = host
        self.port = port

    def _try_connect(self):
        try:
            self.client.connect(self.host, self.port)
        except (mpd.base.ConnectionError, OSError):
            # Already connected, or MPD not reachable: then the next command fails with a logged ConnectionError
            pass

    def __enter__(self):
        self._lock.acquire()
        self._try_connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._lock.release()

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        locked = self._lock.acquire(blocking, timeout)
        if locked:
            self._try_connect()
        return locked

    def release(self):
        self._lock.release()

    def locked(self):
        return self._lock.locked()


class PlayerMPD:
    """Interface to MPD Music Player Daemon"""

    def __init__(self):
        self.nvm = nv_manager()
        self.mpd_host = cfg.getn('playermpd', 'host')
        self.music_player_status = self.nvm.load(cfg.getn('playermpd', 'status_file'))

        self.second_swipe_action_dict = {'toggle': self.toggle,
                                         'play': self.play,
                                         'skip': self.next,
                                         'rewind': self.rewind,
                                         'replay': self.replay,
                                         'replay_if_stopped': self.replay_if_stopped,
                                         'ignore': self._ignore_second_swipe}
        self.second_swipe_action = None
        self.decode_2nd_swipe_option()
        self.play_card_resume = bool(cfg.setndefault('playermpd', 'play_card_resume', value=True))

        self.mpd_client = mpd.MPDClient()
        self.coverart_cache_manager = CoverartCacheManager()

        # The timeout refer to the low-level socket time-out
        # If these are too short and the response is not fast enough (due to the PI being busy),
        # the current MPC command times out. Leave these at blocking calls, since we do not react on a timed out socket
        # in any relevant matter anyway
        self.mpd_client.timeout = None               # network timeout in seconds (floats allowed), default: None
        self.mpd_client.idletimeout = None           # timeout for fetching the result of the idle command
        self.connect()
        logger.info(f"Connected to MPD Version: {self.mpd_client.mpd_version}")

        self.current_folder_status = {}
        if not self.music_player_status:
            self.music_player_status['player_status'] = {}
            self.music_player_status['audio_folder_status'] = {}
            self.music_player_status.save_to_json()
            self.current_folder_status = {}
            self.music_player_status['player_status']['last_played_folder'] = ''
        else:
            last_played_folder = self.music_player_status['player_status'].get('last_played_folder')
            if last_played_folder:
                # current_folder_status is a dict, but last_played_folder a str
                self.current_folder_status = self.music_player_status['audio_folder_status'][last_played_folder]
                # Restore the playlist status in mpd
                # But what about playback position?
                self.mpd_client.clear()
                #  This could fail and cause load fail of entire package:
                # self.mpd_client.add(last_played_folder)
                logger.info(f"Last Played Folder: {last_played_folder}")

        # Clear last folder played, as we actually did not play any folder yet
        # Needed for second swipe detection
        # TODO: This will loose the last_played_folder information is the box is started and closed with playing anything...
        # Change this to last_played_folder and shutdown_state (for restoring)
        self.music_player_status['player_status']['last_played_folder'] = ''

        self.old_song = None
        self.mpd_status = {}
        # For detecting state changes in the status poll (see _track_folder_position)
        self._last_state = None
        self._was_near_playlist_end = False
        self._saved_folder = None
        self.mpd_status_poll_interval = 0.25
        self.mpd_lock = MpdLock(self.mpd_client, self.mpd_host, 6600)
        self.status_is_closing = False
        # self.status_thread = threading.Timer(self.mpd_status_poll_interval, self._mpd_status_poll).start()

        self.status_thread = multitimer.GenericEndlessTimerClass('mpd.timer_status',
                                                                 self.mpd_status_poll_interval, self._mpd_status_poll)
        self.status_thread.start()

    def exit(self):
        logger.debug("Exit routine of playermpd started")
        self.status_is_closing = True
        self.status_thread.cancel()
        self.mpd_client.disconnect()
        self.nvm.save_all()
        return self.status_thread.timer_thread

    def connect(self):
        self.mpd_client.connect(self.mpd_host, 6600)

    def decode_2nd_swipe_option(self):
        cfg_2nd_swipe_action = cfg.setndefault('playermpd', 'second_swipe_action', 'alias', value='none').lower()
        if cfg_2nd_swipe_action not in [*self.second_swipe_action_dict.keys(), 'none', 'custom']:
            logger.error(f"Config mpd.second_swipe_action must be one of "
                         f"{[*self.second_swipe_action_dict.keys(), 'none', 'custom']}. Ignore setting.")
        if cfg_2nd_swipe_action in self.second_swipe_action_dict.keys():
            self.second_swipe_action = self.second_swipe_action_dict[cfg_2nd_swipe_action]
        if cfg_2nd_swipe_action == 'custom':
            custom_action = utils.decode_rpc_call(cfg.getn('playermpd', 'second_swipe_action', default=None))
            self.second_swipe_action = functools.partial(plugs.call_ignore_errors,
                                                         custom_action['package'],
                                                         custom_action['plugin'],
                                                         custom_action['method'],
                                                         custom_action['args'],
                                                         custom_action['kwargs'])

    @staticmethod
    def _ignore_second_swipe():
        logger.debug("Second swipe ignored")

    @plugs.tag
    def get_second_swipe_action(self) -> str:
        """Get the second swipe action (``playermpd.second_swipe_action.alias``), e.g. 'toggle' or 'none'"""
        return str(cfg.getn('playermpd', 'second_swipe_action', 'alias', default='none')).lower()

    @plugs.tag
    def set_second_swipe_action(self, action: str) -> str:
        """
        Set and save the action run when the card of the current folder is swiped again (see :meth:`play_card`)

        :param action: One of 'toggle', 'play', 'skip', 'rewind', 'replay', 'replay_if_stopped', 'ignore', 'none'.
            'ignore' does nothing, 'none' plays the folder again like a first swipe.
        :return: The new action
        """
        action = str(action).lower()
        if action not in [*self.second_swipe_action_dict.keys(), 'none']:
            raise ValueError(f"Unknown second swipe action '{action}'. "
                             f"Must be one of {[*self.second_swipe_action_dict.keys(), 'none']}")
        with cfg:
            cfg.setn('playermpd', 'second_swipe_action', value={'alias': action})
            self.second_swipe_action = self.second_swipe_action_dict.get(action)
            cfg.save(only_if_changed=True)
        logger.info(f"Second swipe action set to '{action}'")
        return action

    @plugs.tag
    def get_play_card_resume(self) -> bool:
        """Get whether cards continue a folder where it was left last time (``playermpd.play_card_resume``)"""
        return self.play_card_resume

    @plugs.tag
    def set_play_card_resume(self, enabled: bool) -> bool:
        """
        Set and save whether cards continue a folder where it was left last time, or always start with the first song

        :param enabled: True: continue at the remembered song and position (see :meth:`play_card`)
        :return: The new setting
        """
        enabled = bool(enabled)
        with cfg:
            cfg.setn('playermpd', 'play_card_resume', value=enabled)
            self.play_card_resume = enabled
            cfg.save(only_if_changed=True)
        logger.info(f"Resume on card swipe {'enabled' if enabled else 'disabled'}")
        return enabled

    def mpd_retry_with_mutex(self, mpd_cmd, *args):
        """
        This method adds thread saftey for acceses to mpd via a mutex lock,
        it shall be used for each access to mpd to ensure thread safety
        In case of a communication error the connection will be reestablished and the pending command will be repeated 2 times

        I think this should be refactored to a decorator
        """
        with self.mpd_lock:
            try:
                value = mpd_cmd(*args)
            except mpd.base.CommandError as e:
                # MPD rejected the command, the connection itself is fine
                logger.error(f"{e.__class__.__qualname__}: {e}")
                value = None
            except Exception as e:
                logger.error(f"{e.__class__.__qualname__}: {e}")
                # The connection may be stuck in the middle of a reply: drop it, MpdLock reconnects on next access
                self.mpd_client.disconnect()
                value = None
        return value

    def _mpd_status_poll(self):
        """
        this method polls the status from mpd and stores the important inforamtion in the music_player_status,
        it will repeat itself in the intervall specified by self.mpd_status_poll_interval
        """
        status = self.mpd_retry_with_mutex(self.mpd_client.status)
        current_song = self.mpd_retry_with_mutex(self.mpd_client.currentsong)
        if status is None or current_song is None:
            # MPD communication failed (already logged). Skip this cycle instead of raising:
            # an exception would end the poll thread and the web app would get no more status updates
            return
        self.mpd_status.update(status)
        self.mpd_status.update(current_song)
        # Use the fresh status/current_song here: self.mpd_status still contains keys of songs played before
        self._track_folder_position(status, current_song)

        # Delete the volume key to avoid confusion
        # Volume is published via the 'volume' component!
        try:
            del self.mpd_status['volume']
        except KeyError:
            pass
        publishing.get_publisher().send('playerstatus', self.mpd_status)

    def _track_folder_position(self, status: dict, current_song: dict):
        """
        Remember song and position of the current folder, so a later :meth:`play_card` continues there

        * Position is only updated while playing or paused. Once stopped, MPD reports the song start, but we want
          to continue where the playback was stopped.
        * When the playlist has played to its end, the position is cleared: the next start begins with the first song.
        * The status file is saved on pause / stop and on folder change, so positions survive a power cut.
        """
        state = status.get('state')
        if state in ('play', 'pause') and 'file' in current_song:
            self.current_folder_status["CURRENTFILENAME"] = current_song['file']
            self.current_folder_status["CURRENTSONGPOS"] = status.get('song', '0')
            self.current_folder_status["ELAPSED"] = status.get('elapsed', '0.0')
            self.current_folder_status["PLAYSTATUS"] = state
            self.current_folder_status["RESUME"] = "OFF"
            self.current_folder_status["SHUFFLE"] = "OFF"
            self.current_folder_status["LOOP"] = "OFF"
            self.current_folder_status["SINGLE"] = "OFF"
            self.music_player_status['player_status']["CURRENTSONGPOS"] = status.get('song', '0')
            self.music_player_status['player_status']["CURRENTFILENAME"] = current_song['file']
        elif state == 'stop' and self._last_state == 'play':
            if self._was_near_playlist_end:
                logger.info("Playlist finished: next start of this folder begins with the first song")
                for key in ('CURRENTFILENAME', 'CURRENTSONGPOS', 'ELAPSED'):
                    self.current_folder_status.pop(key, None)
            self.current_folder_status["PLAYSTATUS"] = 'stop'

        folder = self.music_player_status['player_status'].get('last_played_folder')
        if (state != self._last_state and state in ('pause', 'stop')) or folder != self._saved_folder:
            # Under the lock: play_folder adds folder entries to the status dict (only) while holding it
            with self.mpd_lock:
                self.music_player_status.save_to_json()
            self._saved_folder = folder

        self._was_near_playlist_end = state == 'play' and _is_last_song_ending(status)
        self._last_state = state

    # MPD can play absolute paths but can find songs in its database only by relative path
    # This function aims to prepare the song_url accordingly
    def harmonize_mpd_url(self, song_url):
        _music_library_path_absolute = os.path.expanduser(components.player.get_music_library_path())
        song_url = song_url.replace(f'{_music_library_path_absolute}/', '')

        return song_url

    @plugs.tag
    def get_player_type_and_version(self):
        with self.mpd_lock:
            value = self.mpd_client.mpd_version()
        return value

    @plugs.tag
    def update(self):
        with self.mpd_lock:
            state = self.mpd_client.update()
        return state

    @plugs.tag
    def update_wait(self):
        state = self.update()
        self._db_wait_for_update(state)
        return state

    @plugs.tag
    def play(self):
        with self.mpd_lock:
            self.mpd_client.play()

    @plugs.tag
    def stop(self):
        with self.mpd_lock:
            self.mpd_client.stop()

    @plugs.tag
    def pause(self, state: int = 1):
        """Enforce pause to state (1: pause, 0: resume)

        This is what you want as card removal action: pause the playback, so it can be resumed when card is placed
        on the reader again. What happens on re-placement depends on configured second swipe option
        """
        with self.mpd_lock:
            self.mpd_client.pause(state)

    def _select_song_when_stopped(self, step: int, restart_threshold: Optional[float] = None) -> bool:
        """
        When stopped, select the next / previous song without playing it (like a conventional player)

        MPD cannot select a song without playing it. So the selection is stored as remembered position of the
        current folder, where :meth:`toggle` starts playing.

        :param step: +1 for the next song, -1 for the previous song
        :param restart_threshold: If the remembered position is at least this far into the song, select the start
            of this song instead of the previous one
        :return: False if not stopped, i.e. nothing done
        """
        if self.mpd_client.status().get('state') != 'stop':
            return False
        files = [song['file'] for song in self.mpd_client.playlistinfo()]
        if not files:
            logger.debug("Stopped with empty playlist: nothing to select")
            return True
        filename = self.current_folder_status.get('CURRENTFILENAME')
        if filename in files:
            index = files.index(filename)
            elapsed = float(self.current_folder_status.get('ELAPSED') or 0)
            if restart_threshold is not None and elapsed >= restart_threshold:
                step = 0
            index = min(max(index + step, 0), len(files) - 1)
        else:
            # Playlist has played to its end: next starts with the first, previous with the last song
            index = 0 if step > 0 else len(files) - 1
        self.current_folder_status["CURRENTFILENAME"] = files[index]
        self.current_folder_status["CURRENTSONGPOS"] = str(index)
        self.current_folder_status["ELAPSED"] = '0.0'
        logger.debug(f"Stopped: selected song {index} '{files[index]}'")
        return True

    def _skip_while_paused(self, step: int, restart_threshold: Optional[float] = None) -> bool:
        """
        When paused, go to the start of the next / previous song and stay paused (like a conventional player)

        MPD's next / previous always resume playback, but seeking while paused keeps the pause.

        :param step: +1 for the next song, -1 for the previous song
        :param restart_threshold: If the current song has played for at least this time, go to the start of this
            song instead of the previous one
        :return: False if not paused, i.e. nothing done
        """
        status = self.mpd_client.status()
        if status.get('state') != 'pause':
            return False
        if status.get('random') == '1':
            # The next song is decided by MPD
            if step > 0:
                self.mpd_client.next()
            else:
                self.mpd_client.previous()
        else:
            song = int(status.get('song', 0))
            length = int(status.get('playlistlength', 1))
            if restart_threshold is not None and float(status.get('elapsed', 0)) >= restart_threshold:
                step = 0
            index = song + step
            if status.get('repeat') == '1':
                index %= length
            else:
                index = min(max(index, 0), length - 1)
            logger.debug(f"Paused: go to song {index}")
            self.mpd_client.seek(index, 0)
        if self.mpd_client.status().get('state') != 'pause':
            self.mpd_client.pause(1)
        return True

    @plugs.tag
    def prev(self):
        """Play previous track in current playlist. When stopped or paused, only select it"""
        logger.debug("Prev")
        with self.mpd_lock:
            if not (self._select_song_when_stopped(-1) or self._skip_while_paused(-1)):
                self.mpd_client.previous()

    @plugs.tag
    def prev_or_restart_song(self, restart_threshold: float = 3.0):
        """
        Jump to the start of the current song, or to the previous song if pressed again shortly after (like a CD player)

        When stopped or paused, only select the song and keep stopped / paused (see :meth:`toggle`).

        :param restart_threshold: If the current song has played for less than this time in seconds,
            go to the previous song instead of restarting the current one
        """
        with self.mpd_lock:
            if (self._select_song_when_stopped(-1, restart_threshold)
                    or self._skip_while_paused(-1, restart_threshold)):
                return
            status = self.mpd_client.status()
            if float(status.get('elapsed', 0)) >= restart_threshold:
                logger.debug("Restart song")
                self.mpd_client.seekcur(0)
            else:
                logger.debug("Prev")
                self.mpd_client.previous()

    @plugs.tag
    def next(self):
        """Play next track in current playlist. When stopped or paused, only select it"""
        logger.debug("Next")
        with self.mpd_lock:
            if not (self._select_song_when_stopped(+1) or self._skip_while_paused(+1)):
                self.mpd_client.next()

    @plugs.tag
    def seek(self, new_time):
        with self.mpd_lock:
            self.mpd_client.seekcur(new_time)

    @plugs.tag
    def rewind(self):
        """
        Re-start current playlist from first track

        This also resets the remembered position of the folder (see :meth:`play_card`).

        Note: Will not re-read folder config, but leave settings untouched"""
        logger.debug("Rewind")
        with self.mpd_lock:
            # MPD playlist positions start at 0
            self.mpd_client.play(0)

    @plugs.tag
    def replay(self):
        """
        Re-start playing the last-played folder

        Will reset settings to folder config"""
        logger.debug("Replay")
        with self.mpd_lock:
            self._play_last_folder()

    def _play_last_folder(self):
        folder = self.music_player_status['player_status']['last_played_folder']
        if not folder:
            # E.g. an album or a single song was played last, or nothing since startup
            logger.info("No folder played last: nothing to replay")
            return
        self.play_folder(folder)

    @plugs.tag
    def toggle(self):
        """
        Toggle pause state, i.e. do a pause / resume depending on current state

        When stopped, start playing the loaded playlist again: at the remembered position, which is the song
        selected with next / prev while stopped, or where it was stopped. After the playlist has played to its end,
        start with the first song.
        """
        with self.mpd_lock:
            if self.mpd_client.status().get('state') == 'stop':
                if not self._seek_to_saved_position():
                    self.mpd_client.play()
            else:
                self.mpd_client.pause()

    @plugs.tag
    def replay_if_stopped(self):
        """
        Re-start playing the last-played folder unless playlist is still playing

        > [!NOTE]
        > To me this seems much like the behaviour of play,
        > but we keep it as it is specifically implemented in box 2.X"""
        with self.mpd_lock:
            if self.mpd_status['state'] == 'stop':
                self._play_last_folder()

    # Shuffle
    def _shuffle(self, random):
        # As long as we don't work with waiting lists (aka playlist), this implementation is ok!
        self.mpd_retry_with_mutex(self.mpd_client.random, 1 if random else 0)

    @plugs.tag
    def shuffle(self, option='toggle'):
        if option == 'toggle':
            if self.mpd_status['random'] == '0':
                self._shuffle(1)
            else:
                self._shuffle(0)
        elif option == 'enable':
            self._shuffle(1)
        elif option == 'disable':
            self._shuffle(0)
        else:
            logger.error(f"'{option}' does not exist for 'shuffle'")

    # Repeat
    def _repeatmode(self, mode):
        if mode == 'repeat':
            repeat = 1
            single = 0
        elif mode == 'single':
            repeat = 1
            single = 1
        else:
            repeat = 0
            single = 0

        with self.mpd_lock:
            self.mpd_client.repeat(repeat)
            self.mpd_client.single(single)

    @plugs.tag
    def repeat(self, option='toggle'):
        if option == 'toggle':
            if self.mpd_status['repeat'] == '0':
                self._repeatmode('repeat')
            elif self.mpd_status['repeat'] == '1' and self.mpd_status['single'] == '0':
                self._repeatmode('single')
            else:
                self._repeatmode(None)
        elif option == 'toggle_repeat':
            if self.mpd_status['repeat'] == '0':
                self._repeatmode('repeat')
            else:
                self._repeatmode(None)
        elif option == 'toggle_repeat_single':
            if self.mpd_status['single'] == '0':
                self._repeatmode('single')
            else:
                self._repeatmode(None)
        elif option == 'enable_repeat':
            self._repeatmode('repeat')
        elif option == 'enable_repeat_single':
            self._repeatmode('single')
        elif option == 'disable':
            self._repeatmode(None)
        else:
            logger.error(f"'{option}' does not exist for 'repeat'")

    @plugs.tag
    def get_current_song(self, param):
        return self.mpd_status

    @plugs.tag
    def map_filename_to_playlist_pos(self, filename):
        # self.mpd_client.playlistfind()
        raise NotImplementedError

    @plugs.tag
    def remove(self):
        raise NotImplementedError

    @plugs.tag
    def move(self):
        # song_id = param.get("song_id")
        # step = param.get("step")
        # MPDClient.playlistmove(name, from, to)
        # MPDClient.swapid(song1, song2)
        raise NotImplementedError

    @plugs.tag
    def play_song(self, songid: int):
        """
        Play a song of the current playlist

        The playlist itself is not changed. The song is selected by its MPD song id (``id`` in
        :meth:`playlistinfo`), not by its position: if the playlist has been replaced in the meantime
        (e.g. by a card swipe), the id no longer exists and nothing happens instead of playing a wrong song.

        :param songid: MPD song id
        """
        logger.debug(f"Play song with id {songid}")
        with self.mpd_lock:
            try:
                self.mpd_client.playid(int(songid))
            except mpd.base.CommandError as e:
                logger.warning(f"Song {songid} is no longer in the playlist: {e}")

    def _forget_folder(self):
        """
        Playing something other than a folder (album, single song): no folder is current any more

        So the playback position is not remembered for the folder played before, and a swipe of that
        folder's card is a first swipe (continue the folder) instead of a second swipe (e.g. pause).
        """
        self.music_player_status['player_status']['last_played_folder'] = ''
        self.current_folder_status = {}

    @plugs.tag
    def play_single(self, song_url):
        with self.mpd_lock:
            self._forget_folder()
            self.mpd_client.clear()
            self.mpd_client.addid(song_url)
            self.mpd_client.play()

    @plugs.tag
    def resume(self):
        with self.mpd_lock:
            songpos = self.current_folder_status["CURRENTSONGPOS"]
            elapsed = self.current_folder_status["ELAPSED"]
            self.mpd_client.seek(songpos, elapsed)
            self.mpd_client.play()

    @plugs.tag
    def play_card(self, folder: str, recursive: bool = False):
        """
        Main entry point for trigger music playing from RFID reader. Decodes second swipe options before playing folder content

        * Second swipe: the folder is the current one and is playing or paused. Runs the configured
          second swipe action (``playermpd.second_swipe_action``, e.g. ``toggle`` for pause / resume).
        * First swipe: any other case, e.g. another folder is loaded (from a card or the web app), or this folder
          has been stopped or has played to its end. Plays the folder and, if ``playermpd.play_card_resume`` is
          enabled, continues at the remembered song and position of this folder. A folder that has played to its
          end starts with the first song again.

        :param folder: Folder path relative to music library path
        :param recursive: Add folder recursively
        """
        with self.mpd_lock:
            last_played_folder = self.music_player_status['player_status']['last_played_folder']
            status = self.mpd_retry_with_mutex(self.mpd_client.status) or {}
            is_second_swipe = last_played_folder == folder and status.get('state') in ('play', 'pause')
            logger.debug(f"last_played_folder = {last_played_folder}, state = {status.get('state')}")
            if self.second_swipe_action is not None and is_second_swipe:
                logger.debug('Calling second swipe action')

                # run callbacks before second_swipe_action is invoked
                play_card_callbacks.run_callbacks(folder, PlayCardState.secondSwipe)

                self.second_swipe_action()
            else:
                logger.debug('Calling first swipe action')

                # run callbacks before play_folder is invoked
                play_card_callbacks.run_callbacks(folder, PlayCardState.firstSwipe)

                self.play_folder(folder, recursive, resume=self.play_card_resume)

    @plugs.tag
    def get_single_coverart(self, song_url):
        """
        Saves the album art image to a cache and returns the filename.
        """
        base_filename = slugify(song_url)

        # The status poll thread shares the MPD connection: without the lock, its replies get mixed
        # with the binary picture data, which breaks both
        with self.mpd_lock:
            try:
                metadata_list = self.mpd_client.listallinfo(song_url)
                metadata = {}
                if metadata_list:
                    metadata = metadata_list[0]

                if 'albumartist' in metadata and 'album' in metadata:
                    base_filename = slugify(f"{metadata['albumartist']}-{metadata['album']}")

                cache_filename = self.coverart_cache_manager.find_file_by_hash(base_filename)

                if cache_filename:
                    return cache_filename

                # Cache file does not exist
                # Fetch cover art binary: picture embedded in the song file first,
                # then a cover image in the song's folder (cover.jpg, cover.png, ...)
                album_art_data = self.mpd_client.readpicture(song_url)
                if not album_art_data.get('binary'):
                    try:
                        album_art_data = self.mpd_client.albumart(song_url)
                    except mpd.base.CommandError:
                        # MPD reports a missing cover file as error
                        album_art_data = {}
                if not album_art_data.get('binary'):
                    logger.debug(f"No cover art for {song_url}")
                    return ""

                # Save to cache
                cache_filename = self.coverart_cache_manager.save_to_cache(base_filename, album_art_data)

                return cache_filename

            except mpd.base.CommandError as e:
                logger.error(f"{e.__class__.__qualname__}: {e} at uri {song_url}")
            except Exception as e:
                logger.error(f"{e.__class__.__qualname__}: {e} at uri {song_url}")
                # The connection may be stuck in the middle of a reply: drop it, MpdLock reconnects on next access
                self.mpd_client.disconnect()

        return ""

    @plugs.tag
    def get_album_coverart(self, albumartist: str, album: str):
        song_list = self.list_songs_by_artist_and_album(albumartist, album)

        return self.get_single_coverart(song_list[0]['file'])

    @plugs.tag
    def get_music_library_path(self) -> str:
        """
        Absolute path of the music library (the ``music_directory`` of MPD)

        :meth:`get_folder_content` returns absolute paths below this folder
        """
        return os.path.abspath(os.path.expanduser(components.player.get_music_library_path()))

    @plugs.tag
    def get_folder_content(self, folder: str):
        """
        Get the folder content as content list with meta-information. Depth is always 1.

        Call repeatedly to descend in hierarchy

        :param folder: Folder path relative to music library path (or absolute, as returned by this method)
        :raises ValueError: if the folder is outside of the music library
        """
        library = self.get_music_library_path()
        # No realpath: symlinked folders inside the library stay allowed
        target = os.path.abspath(os.path.join(library, folder))
        if os.path.commonpath([library, target]) != library:
            raise ValueError(f"Folder '{folder}' is outside of the music library")

        plc = playlistgenerator.PlaylistCollector(components.player.get_music_library_path())
        plc.get_directory_content(folder)
        return plc.playlist

    @plugs.tag
    def play_folder(self, folder: str, recursive: bool = False, resume: bool = False,
                    start_song: Optional[str] = None) -> None:
        """
        Playback a music folder.

        Folder content is added to the playlist as described by :mod:`jukebox.playlistgenerator`.
        The playlist is cleared first.

        :param folder: Folder path relative to music library path
        :param recursive: Add folder recursively
        :param resume: Continue at the remembered song and position of this folder instead of the first song
        :param start_song: Start with this song of the folder instead of the first one (path as returned by
            :meth:`get_folder_content`). Takes precedence over ``resume``.
        """
        with self.mpd_lock:
            logger.info(f"Play folder: '{folder}'{' (resume)' if resume else ''}"
                        f"{f' starting at {start_song}' if start_song else ''}")
            self.mpd_client.clear()

            plc = playlistgenerator.PlaylistCollector(components.player.get_music_library_path())
            plc.parse(folder, recursive)
            added = []
            uri = '--unset--'
            try:
                for uri in plc:
                    self.mpd_client.addid(uri)
                    added.append(uri)
            except mpd.base.CommandError as e:
                logger.error(f"{e.__class__.__qualname__}: {e} at uri {uri}")
            except Exception as e:
                logger.error(f"{e.__class__.__qualname__}: {e} at uri {uri}")

            self.music_player_status['player_status']['last_played_folder'] = folder

            self.current_folder_status = self.music_player_status['audio_folder_status'].get(folder)
            if self.current_folder_status is None:
                self.current_folder_status = self.music_player_status['audio_folder_status'][folder] = {}

            start_pos = self._find_in_playlist(added, start_song) if start_song else None
            if start_pos is not None:
                self.mpd_client.play(start_pos)
            elif not (resume and self._seek_to_saved_position()):
                self.mpd_client.play()

    @staticmethod
    def _find_in_playlist(uris, song: str) -> Optional[int]:
        """
        Position of song in the list of uris added to the playlist, or None if it is not in there

        File paths are compared normalized; streams and podcasts (URLs) as they are.
        """
        def normalize(uri):
            return uri if '://' in uri else os.path.normpath(uri)

        wanted = normalize(song)
        for pos, uri in enumerate(uris):
            if uri == song or normalize(uri) == wanted:
                return pos
        logger.info(f"Song '{song}' is not in the folder: start with the first song")
        return None

    def _seek_to_saved_position(self) -> bool:
        """
        Start playback of the loaded folder at its remembered song and position

        :return: False if there is nothing to continue: no position saved, or the song is no longer in the folder
        """
        filename = self.current_folder_status.get('CURRENTFILENAME')
        if not filename:
            return False
        try:
            songs = self.mpd_client.playlistfind('file', filename)
            if not songs:
                logger.info(f"Remembered song '{filename}' is no longer in the folder: start with the first song")
                return False
            elapsed = self.current_folder_status.get('ELAPSED', '0.0')
            logger.info(f"Continue at '{filename}', {elapsed}s")
            self.mpd_client.seek(songs[0]['pos'], elapsed)
        except mpd.base.CommandError as e:
            logger.error(f"Could not continue at remembered position: {e.__class__.__qualname__}: {e}")
            return False
        return True

    @plugs.tag
    def play_album(self, albumartist: str, album: str, start_song: Optional[str] = None):
        """
        Playback a album found in MPD database.

        All album songs are added to the playlist
        The playlist is cleared first.

        :param albumartist: Artist of the Album provided by MPD database
        :param album: Album name provided by MPD database
        :param start_song: Start with this song of the album instead of the first one (``file`` as provided by
            the MPD database)
        """
        with self.mpd_lock:
            logger.info(f"Play album: '{album}' by '{albumartist}"
                        f"{f' starting at {start_song}' if start_song else ''}")
            self._forget_folder()
            self.mpd_client.clear()
            self.mpd_retry_with_mutex(self.mpd_client.findadd, 'albumartist', albumartist, 'album', album)
            songs = self.mpd_client.playlistfind('file', start_song) if start_song else []
            if songs:
                self.mpd_client.play(int(songs[0]['pos']))
            else:
                self.mpd_client.play()

    @plugs.tag
    def queue_load(self, folder):
        # There was something playing before -> stop and save state
        # Clear the queue
        # Check / Create the playlist
        #  - not needed if same folder is played again? Buf what if files have been added a mpc update has been run?
        #  - and this a re-trigger to start the new playlist
        # If we must update the playlists everytime anyway why write them to file and not just keep them in the queue?
        # Load the playlist
        # Get folder config and apply settings
        pass

    @plugs.tag
    def playerstatus(self):
        return self.mpd_status

    @plugs.tag
    def playlistinfo(self):
        with self.mpd_lock:
            value = self.mpd_client.playlistinfo()
        return value

    # Attention: MPD.listal will consume a lot of memory with large libs.. should be refactored at some point
    @plugs.tag
    def list_all_dirs(self):
        with self.mpd_lock:
            result = self.mpd_client.listall()
            # list = [entry for entry in list if 'directory' in entry]
        return result

    @plugs.tag
    def list_albums(self):
        with self.mpd_lock:
            album_list = self.mpd_retry_with_mutex(self.mpd_client.list, 'album', 'group', 'albumartist')

        return album_list

    @plugs.tag
    def list_songs_by_artist_and_album(self, albumartist, album):
        with self.mpd_lock:
            song_list = self.mpd_retry_with_mutex(self.mpd_client.find, 'albumartist', albumartist, 'album', album)

        return song_list

    @plugs.tag
    def list_all_songs(self):
        """
        List all songs of the MPD database, sorted by title

        Each song is reduced to ``file``, ``title``, ``artist``, ``album``, ``albumartist`` and ``duration``
        (missing tags are empty strings). Songs without a title are sorted by their file name.

        :raises RuntimeError: if the MPD database could not be read
        """
        with self.mpd_lock:
            entries = self.mpd_retry_with_mutex(self.mpd_client.listallinfo)

        if entries is None:
            raise RuntimeError("Could not read the song list from MPD")

        songs = [
            {
                'file': entry['file'],
                'title': entry.get('title', ''),
                'artist': entry.get('artist', ''),
                'album': entry.get('album', ''),
                'albumartist': entry.get('albumartist', ''),
                'duration': entry.get('duration', entry.get('time', '')),
            }
            for entry in entries if 'file' in entry
        ]
        songs.sort(key=lambda song: (song['title'] or os.path.basename(song['file'])).casefold())
        return songs

    @plugs.tag
    def get_song_by_url(self, song_url):
        song_url = self.harmonize_mpd_url(song_url)

        with self.mpd_lock:
            song = self.mpd_retry_with_mutex(self.mpd_client.find, 'file', song_url)

        return song

    def get_volume(self):
        """
        Get the current volume

        For volume control do not use directly, but use through the plugin 'volume',
        as the user may have configured a volume control manager other than MPD"""
        with self.mpd_lock:
            volume = self.mpd_client.status().get('volume')
        return int(volume)

    def set_volume(self, volume):
        """
        Set the volume

        For volume control do not use directly, but use through the plugin 'volume',
        as the user may have configured a volume control manager other than MPD"""
        with self.mpd_lock:
            self.mpd_client.setvol(volume)
        return self.get_volume()

    def _db_wait_for_update(self, update_id: int):
        logger.debug("Waiting for update to finish")
        while self._db_is_updating(update_id):
            # a little throttling
            time.sleep(0.1)

    def _db_is_updating(self, update_id: int):
        with self.mpd_lock:
            _status = self.mpd_client.status()
            _cur_update_id = _status.get('updating_db')
            if _cur_update_id is not None and int(_cur_update_id) <= int(update_id):
                return True
            else:
                return False


# ---------------------------------------------------------------------------
# Plugin Initializer / Finalizer
# ---------------------------------------------------------------------------

player_ctrl: PlayerMPD
#: Callback handler instance for play_card events.
#: - is executed when play_card function is called
#: States:
#: - See :class:`PlayCardState`
#: See :class:`PlayContentCallbacks`
play_card_callbacks: PlayContentCallbacks[PlayCardState]


@plugs.initialize
def initialize():
    global player_ctrl
    player_ctrl = PlayerMPD()
    plugs.register(player_ctrl, name='ctrl')

    global play_card_callbacks
    play_card_callbacks = PlayContentCallbacks[PlayCardState]('play_card_callbacks', logger, context=player_ctrl.mpd_lock)

    # Update mpc library
    library_update = cfg.setndefault('playermpd', 'library', 'update_on_startup', value=True)
    if library_update:
        player_ctrl.update()

    # Check user rights on music library
    library_check_user_rights = cfg.setndefault('playermpd', 'library', 'check_user_rights', value=True)
    if library_check_user_rights is True:
        music_library_path = components.player.get_music_library_path()
        if music_library_path is not None:
            logger.info(f"Change user rights for {music_library_path}")
            misc.recursive_chmod(music_library_path, mode_files=0o666, mode_dirs=0o777)


@plugs.atexit
def atexit(**ignored_kwargs):
    global player_ctrl
    return player_ctrl.exit()
