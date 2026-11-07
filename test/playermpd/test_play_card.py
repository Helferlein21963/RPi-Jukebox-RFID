# RPi-Jukebox-RFID Version 3
# Copyright (c) See file LICENSE in project root folder
"""Tests for the swipe logic in PlayerMPD.play_card and for remembering the position per folder"""
import os
import sys
import threading
from unittest import mock

import pytest

# In case this is run locally from
sys.path.append(os.path.abspath('../../src/jukebox'))
import jukebox.plugs as plugs  # noqa: E402

plugs.ALLOW_DIRECT_IMPORTS = True
import components.playermpd as playermpd  # noqa: E402

FOLDER_A = '/music/A'
FOLDER_B = '/music/B'


class StatusDict(dict):
    """Stands in for the nv_dict that holds music_player_status"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.save_to_json = mock.Mock()


class FakePlaylistCollector:
    def __init__(self, library_path):
        self.folder = None

    def parse(self, folder, recursive):
        self.folder = folder

    def __iter__(self):
        name = os.path.basename(self.folder)
        return iter([f"{name}/01.mp3", f"{name}/02.mp3", f"{name}/03.mp3"])


@pytest.fixture
def player(monkeypatch):
    monkeypatch.setattr(playermpd.playlistgenerator, 'PlaylistCollector', FakePlaylistCollector)
    monkeypatch.setattr(playermpd.components.player, 'get_music_library_path', lambda: '/music')
    monkeypatch.setattr(playermpd, 'play_card_callbacks', mock.Mock(), raising=False)

    p = playermpd.PlayerMPD.__new__(playermpd.PlayerMPD)
    p.mpd_client = mock.Mock()
    p.mpd_client.playlistfind.return_value = []
    p.mpd_lock = threading.RLock()
    p.music_player_status = StatusDict(
        player_status={'last_played_folder': ''},
        audio_folder_status={
            FOLDER_A: {'CURRENTFILENAME': 'A/02.mp3', 'CURRENTSONGPOS': '1', 'ELAPSED': '42.5'},
        })
    p.current_folder_status = {}
    p.second_swipe_action = mock.Mock()
    p.play_card_resume = True
    p._last_state = None
    p._was_near_playlist_end = False
    p._saved_folder = None
    return p


def set_state(p, state, folder=None):
    p.mpd_client.status.return_value = {'state': state}
    if folder is not None:
        p.music_player_status['player_status']['last_played_folder'] = folder


def test_first_swipe_continues_at_saved_position(player):
    set_state(player, 'play', FOLDER_B)
    player.mpd_client.playlistfind.return_value = [{'file': 'A/02.mp3', 'pos': '1'}]

    player.play_card(FOLDER_A)

    player.mpd_client.clear.assert_called_once()
    player.mpd_client.playlistfind.assert_called_once_with('file', 'A/02.mp3')
    player.mpd_client.seek.assert_called_once_with('1', '42.5')
    player.mpd_client.play.assert_not_called()
    player.second_swipe_action.assert_not_called()
    assert player.music_player_status['player_status']['last_played_folder'] == FOLDER_A


@pytest.mark.parametrize('state', ['play', 'pause'])
def test_second_swipe_while_playing_or_paused(player, state):
    set_state(player, state, FOLDER_A)

    player.play_card(FOLDER_A)

    player.second_swipe_action.assert_called_once()
    player.mpd_client.clear.assert_not_called()


def test_same_folder_stopped_continues_like_first_swipe(player):
    set_state(player, 'stop', FOLDER_A)
    player.mpd_client.playlistfind.return_value = [{'file': 'A/02.mp3', 'pos': '1'}]

    player.play_card(FOLDER_A)

    player.second_swipe_action.assert_not_called()
    player.mpd_client.seek.assert_called_once_with('1', '42.5')


def test_folder_without_saved_position_starts_with_first_song(player):
    set_state(player, 'stop', FOLDER_A)

    player.play_card(FOLDER_B)

    player.mpd_client.seek.assert_not_called()
    player.mpd_client.play.assert_called_once_with()


def test_saved_song_no_longer_in_folder_starts_with_first_song(player):
    set_state(player, 'stop', '')
    player.mpd_client.playlistfind.return_value = []

    player.play_card(FOLDER_A)

    player.mpd_client.seek.assert_not_called()
    player.mpd_client.play.assert_called_once_with()


def test_resume_disabled_starts_with_first_song(player):
    set_state(player, 'play', FOLDER_B)
    player.play_card_resume = False

    player.play_card(FOLDER_A)

    player.mpd_client.seek.assert_not_called()
    player.mpd_client.play.assert_called_once_with()


@pytest.fixture
def jukebox_cfg(monkeypatch):
    handler = playermpd.cfg
    handler.config_dict({'playermpd': {'second_swipe_action': {'alias': 'toggle'}, 'play_card_resume': True}})
    monkeypatch.setattr(handler, 'save', mock.Mock())
    return handler


def test_set_second_swipe_action(player, jukebox_cfg):
    player.second_swipe_action_dict = {'toggle': mock.Mock(), 'ignore': mock.Mock()}

    assert player.set_second_swipe_action('IGNORE') == 'ignore'

    assert player.get_second_swipe_action() == 'ignore'
    assert player.second_swipe_action is player.second_swipe_action_dict['ignore']
    jukebox_cfg.save.assert_called_once()


def test_set_second_swipe_action_none_disables_second_swipe(player, jukebox_cfg):
    player.second_swipe_action_dict = {'toggle': mock.Mock()}

    player.set_second_swipe_action('none')

    assert player.second_swipe_action is None
    assert jukebox_cfg.getn('playermpd', 'second_swipe_action', 'alias') == 'none'


def test_set_second_swipe_action_rejects_unknown(player, jukebox_cfg):
    player.second_swipe_action_dict = {'toggle': mock.Mock()}

    with pytest.raises(ValueError):
        player.set_second_swipe_action('explode')
    assert player.get_second_swipe_action() == 'toggle'


def test_set_play_card_resume(player, jukebox_cfg):
    assert player.set_play_card_resume(False) is False

    assert player.get_play_card_resume() is False
    assert jukebox_cfg.getn('playermpd', 'play_card_resume') is False
    jukebox_cfg.save.assert_called_once()


def test_ignore_second_swipe_does_nothing(player):
    set_state(player, 'play', FOLDER_A)
    player.second_swipe_action = player._ignore_second_swipe

    player.play_card(FOLDER_A)

    player.mpd_client.clear.assert_not_called()
    player.mpd_client.pause.assert_not_called()


def test_play_folder_from_web_app_starts_with_first_song(player):
    player.play_folder(FOLDER_A)

    player.mpd_client.seek.assert_not_called()
    player.mpd_client.play.assert_called_once_with()


@pytest.mark.parametrize('resume', [False, True])
def test_play_folder_starts_at_selected_song(player, resume):
    player.mpd_client.playlistfind.return_value = [{'file': 'A/02.mp3', 'pos': '1'}]

    player.play_folder(FOLDER_A, resume=resume, start_song='A/03.mp3')

    player.mpd_client.play.assert_called_once_with(2)
    player.mpd_client.seek.assert_not_called()
    assert player.music_player_status['player_status']['last_played_folder'] == FOLDER_A


def test_play_folder_compares_normalized_paths(player):
    player.play_folder(FOLDER_A, start_song='A/./sub/../02.mp3')

    player.mpd_client.play.assert_called_once_with(1)


def test_play_folder_unknown_start_song_starts_with_first_song(player):
    player.play_folder(FOLDER_A, start_song='A/99.mp3')

    player.mpd_client.play.assert_called_once_with()


def test_play_song_plays_song_by_id(player):
    player.play_song('17')

    player.mpd_client.playid.assert_called_once_with(17)
    player.mpd_client.clear.assert_not_called()


def test_play_song_no_longer_in_playlist_does_nothing(player):
    # The playlist was replaced (e.g. card swipe) before the click in the web app arrived
    player.mpd_client.playid.side_effect = playermpd.mpd.base.CommandError('No such song')

    player.play_song('17')

    player.mpd_client.play.assert_not_called()


@pytest.mark.parametrize('play_other', [
    lambda p: p.play_album('Artist', 'Album'),
    lambda p: p.play_single('Artist/Album/01.mp3'),
])
def test_album_or_single_song_keeps_folder_position(player, play_other):
    player.mpd_retry_with_mutex = mock.Mock()
    folder_status = start_folder_a(player)

    play_other(player)
    poll(player, 'play', song='5', elapsed='10.0', file='Artist/Album/06.mp3')

    assert folder_status['CURRENTFILENAME'] == 'A/02.mp3'
    assert folder_status['ELAPSED'] == '42.5'
    assert player.music_player_status['player_status']['last_played_folder'] == ''


def test_card_after_album_is_first_swipe(player):
    player.mpd_retry_with_mutex = mock.Mock(return_value={'state': 'play'})
    start_folder_a(player)
    player.play_album('Artist', 'Album')
    player.mpd_client.reset_mock()
    player.mpd_client.playlistfind.return_value = [{'file': 'A/02.mp3', 'pos': '1'}]

    player.play_card(FOLDER_A)

    player.second_swipe_action.assert_not_called()
    player.mpd_client.seek.assert_called_once_with('1', '42.5')


def test_replay_without_last_folder_does_nothing(player):
    player.replay()

    player.mpd_client.clear.assert_not_called()


def test_play_album_starts_at_selected_song(player):
    player.mpd_retry_with_mutex = mock.Mock()
    player.mpd_client.playlistfind.return_value = [{'file': 'Artist/Album/02.mp3', 'pos': '1'}]

    player.play_album('Artist', 'Album', start_song='Artist/Album/02.mp3')

    player.mpd_client.playlistfind.assert_called_once_with('file', 'Artist/Album/02.mp3')
    player.mpd_client.play.assert_called_once_with(1)


def test_play_album_without_start_song_starts_with_first_song(player):
    player.mpd_retry_with_mutex = mock.Mock()

    player.play_album('Artist', 'Album')

    player.mpd_client.playlistfind.assert_not_called()
    player.mpd_client.play.assert_called_once_with()


@pytest.mark.parametrize('state', ['play', 'pause'])
def test_toggle_pauses_and_resumes(player, state):
    player.mpd_client.status.return_value = {'state': state}

    player.toggle()

    player.mpd_client.pause.assert_called_once_with()
    player.mpd_client.play.assert_not_called()


def test_toggle_when_stopped_continues_at_saved_position(player):
    player.mpd_client.status.return_value = {'state': 'stop'}
    player.current_folder_status = player.music_player_status['audio_folder_status'][FOLDER_A]
    player.mpd_client.playlistfind.return_value = [{'file': 'A/02.mp3', 'pos': '1'}]

    player.toggle()

    player.mpd_client.seek.assert_called_once_with('1', '42.5')
    player.mpd_client.pause.assert_not_called()


def test_toggle_when_stopped_without_position_plays(player):
    player.mpd_client.status.return_value = {'state': 'stop'}

    player.toggle()

    player.mpd_client.seek.assert_not_called()
    player.mpd_client.play.assert_called_once_with()


PLAYLIST_A = [{'file': 'A/01.mp3'}, {'file': 'A/02.mp3'}, {'file': 'A/03.mp3'}]


def stopped_at(player, filename=None, elapsed='0.0'):
    """MPD is stopped with playlist A loaded; filename is the remembered song (None: playlist played to its end)"""
    player.mpd_client.status.return_value = {'state': 'stop'}
    player.mpd_client.playlistinfo.return_value = PLAYLIST_A
    player.current_folder_status = {'CURRENTFILENAME': filename, 'ELAPSED': elapsed} if filename else {}
    return player.current_folder_status


@pytest.mark.parametrize('method, start, expected', [
    ('next', 'A/02.mp3', 'A/03.mp3'),
    ('next', 'A/03.mp3', 'A/03.mp3'),   # stays at the last song
    ('next', None, 'A/01.mp3'),         # after the end of the playlist: first song
    ('prev', 'A/02.mp3', 'A/01.mp3'),
    ('prev', 'A/01.mp3', 'A/01.mp3'),   # stays at the first song
    ('prev', None, 'A/03.mp3'),         # after the end of the playlist: last song
])
def test_next_prev_when_stopped_only_select_song(player, method, start, expected):
    folder_status = stopped_at(player, start, elapsed='12.0')

    getattr(player, method)()

    assert folder_status['CURRENTFILENAME'] == expected
    assert folder_status['ELAPSED'] == '0.0'
    for mpd_call in ('next', 'previous', 'play', 'seek', 'seekcur'):
        getattr(player.mpd_client, mpd_call).assert_not_called()


@pytest.mark.parametrize('elapsed, expected', [
    ('42.0', 'A/02.mp3'),   # stopped within the song: back to its start
    ('0.0', 'A/01.mp3'),    # already at the start: previous song
])
def test_prev_or_restart_song_when_stopped(player, elapsed, expected):
    folder_status = stopped_at(player, 'A/02.mp3', elapsed=elapsed)

    player.prev_or_restart_song()

    assert folder_status['CURRENTFILENAME'] == expected
    assert folder_status['ELAPSED'] == '0.0'
    player.mpd_client.previous.assert_not_called()


def test_toggle_plays_song_selected_while_stopped(player):
    stopped_at(player, 'A/02.mp3')
    player.next()
    player.mpd_client.playlistfind.return_value = [{'file': 'A/03.mp3', 'pos': '2'}]

    player.toggle()

    player.mpd_client.playlistfind.assert_called_once_with('file', 'A/03.mp3')
    player.mpd_client.seek.assert_called_once_with('2', '0.0')


def paused_at(player, song, elapsed='12.0', length='3', repeat='0', random='0'):
    player.mpd_client.status.return_value = {'state': 'pause', 'song': song, 'elapsed': elapsed,
                                             'playlistlength': length, 'repeat': repeat, 'random': random}


@pytest.mark.parametrize('method, song, repeat, expected', [
    ('next', '1', '0', 2),
    ('next', '2', '0', 2),      # stays at the last song
    ('next', '2', '1', 0),      # repeat: wraps to the first song
    ('prev', '1', '0', 0),
    ('prev', '0', '0', 0),      # stays at the first song
    ('prev', '0', '1', 2),      # repeat: wraps to the last song
])
def test_next_prev_when_paused_stay_paused(player, method, song, repeat, expected):
    paused_at(player, song, repeat=repeat)

    getattr(player, method)()

    player.mpd_client.seek.assert_called_once_with(expected, 0)
    for mpd_call in ('next', 'previous', 'play', 'pause'):
        getattr(player.mpd_client, mpd_call).assert_not_called()


@pytest.mark.parametrize('elapsed, expected', [('10.0', 1), ('1.0', 0)])
def test_prev_or_restart_song_when_paused(player, elapsed, expected):
    paused_at(player, '1', elapsed=elapsed)

    player.prev_or_restart_song()

    player.mpd_client.seek.assert_called_once_with(expected, 0)
    player.mpd_client.seekcur.assert_not_called()


def test_next_when_paused_pauses_again_if_mpd_started_playing(player):
    paused_at(player, '0')
    status = dict(player.mpd_client.status.return_value)
    # status is read: stopped check, paused check, check after the seek
    player.mpd_client.status.side_effect = [status, status, {**status, 'state': 'play'}]

    player.next()

    player.mpd_client.pause.assert_called_once_with(1)


def test_next_when_paused_with_random_uses_mpd_next(player):
    paused_at(player, '0', random='1')
    status = dict(player.mpd_client.status.return_value)
    player.mpd_client.status.side_effect = [status, status, {**status, 'state': 'play'}]

    player.next()

    player.mpd_client.next.assert_called_once_with()
    player.mpd_client.pause.assert_called_once_with(1)


def test_next_when_stopped_with_empty_playlist_does_nothing(player):
    player.mpd_client.status.return_value = {'state': 'stop'}
    player.mpd_client.playlistinfo.return_value = []

    player.next()

    player.mpd_client.next.assert_not_called()


def test_rewind_starts_first_song():
    p = playermpd.PlayerMPD.__new__(playermpd.PlayerMPD)
    p.mpd_client = mock.Mock()
    p.mpd_lock = threading.RLock()
    p.rewind()
    p.mpd_client.play.assert_called_once_with(0)


@pytest.mark.parametrize('state, elapsed, expected', [
    ('play', '10.0', 'seekcur'),    # song is playing for a while: back to its start
    ('play', '3.0', 'seekcur'),
    ('play', '2.9', 'previous'),    # pressed again right after the restart: previous song
])
def test_prev_or_restart_song(state, elapsed, expected):
    p = playermpd.PlayerMPD.__new__(playermpd.PlayerMPD)
    p.mpd_client = mock.Mock()
    p.mpd_lock = threading.RLock()
    p.mpd_client.status.return_value = {'state': state, **({'elapsed': elapsed} if elapsed else {})}

    p.prev_or_restart_song()

    if expected == 'seekcur':
        p.mpd_client.seekcur.assert_called_once_with(0)
        p.mpd_client.previous.assert_not_called()
    else:
        p.mpd_client.previous.assert_called_once_with()
        p.mpd_client.seekcur.assert_not_called()


def poll(p, state, song=None, playlistlength='3', elapsed=None, duration='100.0', file=None):
    status = {'state': state, 'playlistlength': playlistlength}
    if song is not None:
        status['song'] = song
    if elapsed is not None:
        status['elapsed'] = elapsed
        status['duration'] = duration
    current_song = {'file': file} if file else {}
    p._track_folder_position(status, current_song)


def start_folder_a(p):
    p.music_player_status['player_status']['last_played_folder'] = FOLDER_A
    p.current_folder_status = p.music_player_status['audio_folder_status'][FOLDER_A]
    return p.current_folder_status


def test_position_is_tracked_while_playing(player):
    folder_status = start_folder_a(player)
    poll(player, 'play', song='2', elapsed='10.0', file='A/03.mp3')

    assert folder_status['CURRENTFILENAME'] == 'A/03.mp3'
    assert folder_status['CURRENTSONGPOS'] == '2'
    assert folder_status['ELAPSED'] == '10.0'


def test_stop_keeps_position_where_it_was_stopped(player):
    folder_status = start_folder_a(player)
    poll(player, 'play', song='1', elapsed='50.0', file='A/02.mp3')
    # MPD resets elapsed when stopped, but keeps the current song
    poll(player, 'stop', song='1', file='A/02.mp3')
    poll(player, 'stop', song='1', file='A/02.mp3')

    assert folder_status['CURRENTFILENAME'] == 'A/02.mp3'
    assert folder_status['ELAPSED'] == '50.0'
    assert folder_status['PLAYSTATUS'] == 'stop'


def test_playlist_played_to_end_clears_position(player):
    folder_status = start_folder_a(player)
    poll(player, 'play', song='2', elapsed='99.5', duration='100.0', file='A/03.mp3')
    poll(player, 'stop')
    poll(player, 'stop')

    assert 'CURRENTFILENAME' not in folder_status
    assert 'ELAPSED' not in folder_status


def test_stop_during_last_song_keeps_position(player):
    folder_status = start_folder_a(player)
    poll(player, 'play', song='2', elapsed='30.0', duration='100.0', file='A/03.mp3')
    poll(player, 'stop', song='2', file='A/03.mp3')

    assert folder_status['CURRENTFILENAME'] == 'A/03.mp3'
    assert folder_status['ELAPSED'] == '30.0'


def test_stopped_at_startup_keeps_position(player):
    folder_status = start_folder_a(player)
    poll(player, 'stop')

    assert folder_status['CURRENTFILENAME'] == 'A/02.mp3'


def test_status_saved_on_pause_and_folder_change(player):
    start_folder_a(player)
    poll(player, 'play', song='1', elapsed='1.0', file='A/02.mp3')
    assert player.music_player_status.save_to_json.call_count == 1   # folder changed
    poll(player, 'play', song='1', elapsed='1.5', file='A/02.mp3')
    assert player.music_player_status.save_to_json.call_count == 1
    poll(player, 'pause', song='1', elapsed='1.6', file='A/02.mp3')
    assert player.music_player_status.save_to_json.call_count == 2
