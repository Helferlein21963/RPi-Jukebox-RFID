# RPi-Jukebox-RFID Version 3
# Copyright (c) See file LICENSE in project root folder
"""Tests for the library methods of PlayerMPD used by the web app: list_all_songs, get_folder_content,
get_folder_coverart"""
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


@pytest.fixture
def player():
    p = playermpd.PlayerMPD.__new__(playermpd.PlayerMPD)
    p.mpd_client = mock.Mock()
    p.mpd_lock = threading.RLock()
    return p


def test_only_songs_with_reduced_fields(player):
    player.mpd_client.listallinfo.return_value = [
        {'directory': 'A'},
        {'file': 'A/01.mp3', 'title': 'Song', 'artist': 'Artist', 'album': 'Album',
         'albumartist': 'Album Artist', 'duration': '123.4', 'track': '1', 'genre': 'Pop',
         'last-modified': '2026-11-08T10:00:00Z'},
        {'playlist': 'list.m3u'},
    ]

    assert player.list_all_songs() == [
        {'file': 'A/01.mp3', 'title': 'Song', 'artist': 'Artist', 'album': 'Album',
         'albumartist': 'Album Artist', 'duration': '123.4', 'modified': '2026-11-08T10:00:00Z'},
    ]


def test_missing_tags_are_empty_and_time_is_fallback_for_duration(player):
    player.mpd_client.listallinfo.return_value = [{'file': 'B/02.mp3', 'time': '61'}]

    assert player.list_all_songs() == [
        {'file': 'B/02.mp3', 'title': '', 'artist': '', 'album': '', 'albumartist': '', 'duration': '61',
         'modified': ''},
    ]


def test_sorted_by_title_or_file_name_ignoring_case(player):
    player.mpd_client.listallinfo.return_value = [
        {'file': 'x/zebra.mp3', 'title': 'zebra'},
        {'file': 'y/Banana.mp3'},
        {'file': 'z/whatever.mp3', 'title': 'Apple'},
    ]

    assert [song['file'] for song in player.list_all_songs()] == ['z/whatever.mp3', 'y/Banana.mp3', 'x/zebra.mp3']


def test_mpd_error_raises(player):
    player.mpd_client.listallinfo.side_effect = OSError('connection lost')

    with pytest.raises(RuntimeError):
        player.list_all_songs()


@pytest.fixture
def library(monkeypatch, tmp_path):
    music = tmp_path / 'audiofolders'
    (music / 'Conni').mkdir(parents=True)
    (music / 'Conni' / '01.mp3').write_text('')
    (tmp_path / 'settings').mkdir()
    monkeypatch.setattr(playermpd.components.player, 'get_music_library_path', lambda: str(music))
    return music


@pytest.mark.parametrize('folder', ['./', 'Conni', '{library}', '{library}/Conni', 'Conni/../Conni'])
def test_folder_content_inside_library(player, library, folder):
    content = player.get_folder_content(folder.format(library=library))

    assert isinstance(content, list)


@pytest.mark.parametrize('folder', ['..', '../settings', 'Conni/../..', '/', '{library}/..'])
def test_folder_content_outside_library_is_refused(player, library, folder):
    with pytest.raises(ValueError):
        player.get_folder_content(folder.format(library=library))


def test_music_library_path_is_absolute(player, library):
    assert player.get_music_library_path() == str(library)


def test_folder_coverart_uses_first_song(player, library):
    (library / 'Conni' / 'Teil 2').mkdir()
    player.mpd_client.listall.return_value = [
        {'directory': 'Conni/Teil 2'},
        {'file': 'Conni/Teil 2/01.mp3'},
        {'file': 'Conni/01.mp3'},
    ]
    player.get_single_coverart = mock.Mock(return_value='conni.jpg')

    assert player.get_folder_coverart(f'{library}/Conni/') == 'conni.jpg'
    player.mpd_client.listall.assert_called_once_with('Conni')
    player.get_single_coverart.assert_called_once_with('Conni/01.mp3')


@pytest.mark.parametrize('folder', ['Missing', '..', './'])
def test_folder_coverart_without_folder_is_empty(player, library, folder):
    player.get_single_coverart = mock.Mock()

    assert player.get_folder_coverart(folder) == ''
    player.mpd_client.listall.assert_not_called()
    player.get_single_coverart.assert_not_called()


def test_folder_coverart_without_songs_is_empty(player, library):
    player.mpd_client.listall.return_value = [{'directory': 'Conni/Leer'}]
    player.get_single_coverart = mock.Mock()

    assert player.get_folder_coverart('Conni') == ''
    player.get_single_coverart.assert_not_called()
