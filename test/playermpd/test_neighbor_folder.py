# RPi-Jukebox-RFID Version 3
# Copyright (c) See file LICENSE in project root folder
"""Tests for switching to the next / previous folder: library_edit.neighbor_folder and PlayerMPD.play_next_folder"""
import os
import sys
import threading
from unittest import mock

import pytest

# In case this is run locally from
sys.path.append(os.path.abspath('../../src/jukebox'))
import jukebox.plugs as plugs  # noqa: E402
import jukebox.library_edit as library_edit  # noqa: E402

plugs.ALLOW_DIRECT_IMPORTS = True
import components.playermpd as playermpd  # noqa: E402


@pytest.fixture
def music(tmp_path):
    """Library: Hoerspiele/{Folge_01, folge_02, Folge_03 (empty), Folge_04 (only a sub-folder), .hidden}, Musik"""
    lib = tmp_path / 'audiofolders'
    series = lib / 'Hoerspiele'
    for name in ('Folge_01', 'folge_02', 'Folge_03', '.hidden'):
        (series / name).mkdir(parents=True)
    for name in ('Folge_01', 'folge_02', '.hidden'):
        (series / name / '01.mp3').write_text('x')
    (series / 'Folge_03' / 'cover.jpg').write_text('x')
    (series / 'Folge_04' / 'CD1').mkdir(parents=True)
    (series / 'Folge_04' / 'CD1' / '01.mp3').write_text('x')
    (series / 'notes.txt').write_text('x')
    (lib / 'Musik').mkdir()
    (lib / 'Musik' / 'song.mp3').write_text('x')
    return str(lib)


def names(paths):
    return os.path.basename(paths) if paths else paths


# ---------------------------------------------------------------------------
# library_edit.neighbor_folder
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('folder, step, expected', [
    ('Hoerspiele/Folge_01', 1, 'folge_02'),
    ('Hoerspiele/folge_02', 1, 'Folge_03'),
    ('Hoerspiele/Folge_04', 1, 'Folge_01'),
    ('Hoerspiele/Folge_01', -1, 'Folge_04'),
    ('Hoerspiele/folge_02/', -1, 'Folge_01'),
    ('Hoerspiele/Folge_02b', 1, 'Folge_03'),
    ('Hoerspiele/Folge_02b', -1, 'folge_02'),
    ('Hoerspiele', 1, 'Musik'),
    ('Musik', -1, 'Hoerspiele'),
])
def test_neighbor_folder(music, folder, step, expected):
    assert names(library_edit.neighbor_folder(music, folder, step)) == expected


def test_neighbor_folder_absolute_path(music):
    result = library_edit.neighbor_folder(music, os.path.join(music, 'Hoerspiele', 'Folge_01'), 1)
    assert result == os.path.join(music, 'Hoerspiele', 'folge_02')


def test_neighbor_folder_skips_rejected(music):
    def is_playable(path):
        return not path.endswith('Folge_03')

    assert names(library_edit.neighbor_folder(music, 'Hoerspiele/folge_02', 1, is_playable)) == 'Folge_04'


def test_neighbor_folder_none_playable(music):
    assert library_edit.neighbor_folder(music, 'Hoerspiele/Folge_01', 1, lambda path: False) is None


def test_neighbor_folder_only_child(music):
    os.mkdir(os.path.join(music, 'Musik', 'Single'))
    assert library_edit.neighbor_folder(music, 'Musik/Single', 1) is None


@pytest.mark.parametrize('folder', ['', '.', '..', '../outside', '/etc'])
def test_neighbor_folder_outside_library(music, folder):
    with pytest.raises(ValueError):
        library_edit.neighbor_folder(music, folder, 1)


# ---------------------------------------------------------------------------
# PlayerMPD.play_next_folder / play_prev_folder
# ---------------------------------------------------------------------------

@pytest.fixture
def player(music, monkeypatch):
    monkeypatch.setattr(playermpd.components.player, 'get_music_library_path', lambda: music)
    p = playermpd.PlayerMPD.__new__(playermpd.PlayerMPD)
    p.mpd_client = mock.Mock()
    p.mpd_client.currentsong.return_value = {}
    p.mpd_lock = threading.RLock()
    p.music_player_status = {'player_status': {'last_played_folder': ''}, 'audio_folder_status': {}}
    p.current_folder_status = {}
    p.play_card_resume = True
    p.play_folder = mock.Mock()
    return p


def test_play_next_folder_skips_folder_without_songs(player):
    player.music_player_status['player_status']['last_played_folder'] = 'Hoerspiele/folge_02'

    # Folge_03 has no songs, Folge_04 only in a sub-folder (played recursively)
    assert player.play_next_folder() == os.path.join('Hoerspiele', 'Folge_04')
    player.play_folder.assert_called_once_with(os.path.join('Hoerspiele', 'Folge_04'), recursive=True, resume=True)


def test_play_prev_folder(player):
    player.music_player_status['player_status']['last_played_folder'] = 'Hoerspiele/Folge_01'
    player.play_card_resume = False

    assert player.play_prev_folder() == os.path.join('Hoerspiele', 'Folge_04')
    player.play_folder.assert_called_once_with(os.path.join('Hoerspiele', 'Folge_04'), recursive=True, resume=False)


def test_play_next_folder_keeps_absolute_form(player, music):
    player.music_player_status['player_status']['last_played_folder'] = os.path.join(music, 'Hoerspiele', 'Folge_01')

    assert player.play_next_folder() == os.path.join(music, 'Hoerspiele', 'folge_02')


def test_play_next_folder_from_current_song(player):
    player.mpd_client.currentsong.return_value = {'file': 'Hoerspiele/Folge_01/01.mp3'}

    assert player.play_next_folder() == os.path.join('Hoerspiele', 'folge_02')


@pytest.mark.parametrize('song', [{}, {'file': 'http://radio.example/stream'}, {'file': 'song.mp3'}])
def test_play_next_folder_without_current_folder(player, song):
    player.mpd_client.currentsong.return_value = song

    assert player.play_next_folder() is None
    player.play_folder.assert_not_called()


def test_play_next_folder_vanished_parent(player):
    player.music_player_status['player_status']['last_played_folder'] = 'Gone/Folder'

    assert player.play_next_folder() is None
    player.play_folder.assert_not_called()
