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


def test_play_folder_from_web_app_starts_with_first_song(player):
    player.play_folder(FOLDER_A)

    player.mpd_client.seek.assert_not_called()
    player.mpd_client.play.assert_called_once_with()


def test_rewind_starts_first_song():
    p = playermpd.PlayerMPD.__new__(playermpd.PlayerMPD)
    p.mpd_client = mock.Mock()
    p.mpd_lock = threading.RLock()
    p.rewind()
    p.mpd_client.play.assert_called_once_with(0)


@pytest.mark.parametrize('state, elapsed, expected', [
    ('play', '10.0', 'seekcur'),    # song is playing for a while: back to its start
    ('pause', '10.0', 'seekcur'),
    ('play', '3.0', 'seekcur'),
    ('play', '2.9', 'previous'),    # pressed again right after the restart: previous song
    ('stop', None, 'previous'),
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
