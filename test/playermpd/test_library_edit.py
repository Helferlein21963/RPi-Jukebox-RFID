# RPi-Jukebox-RFID Version 3
# Copyright (c) See file LICENSE in project root folder
"""Tests for renaming folders and songs of the music library: jukebox.library_edit and PlayerMPD.rename"""
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


# ---------------------------------------------------------------------------
# library_edit
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('name, expected', [
    ('Max übernachtet bei Oma', 'Max übernachtet bei Oma'),
    ('  a   b  ', 'a b'),
    ('AC/DC: Best?', 'AC DC Best'),
    ('..hidden..', 'hidden'),
    ('../../etc', 'etc'),
])
def test_clean_name(name, expected):
    assert library_edit.clean_name(name) == expected


@pytest.mark.parametrize('name', ['', '   ', '..', '/', None])
def test_clean_name_rejects_empty(name):
    with pytest.raises(ValueError):
        library_edit.clean_name(name)


@pytest.fixture
def music(tmp_path):
    lib = tmp_path / 'audiofolders'
    (lib / 'Conni' / 'CD 1').mkdir(parents=True)
    (lib / 'Conni' / '01.mp3').write_text('')
    (lib / 'Other').mkdir()
    return str(lib)


@pytest.mark.parametrize('path', ['Conni', '{lib}/Conni', 'Conni/01.mp3', 'Conni/../Other'])
def test_resolve_in_library(music, path):
    assert os.path.exists(library_edit.resolve_in_library(music, path.format(lib=music)))


@pytest.mark.parametrize('path', ['./', '{lib}', '..', '{lib}/..', '/etc'])
def test_resolve_outside_library_or_root_raises(music, path):
    with pytest.raises(ValueError):
        library_edit.resolve_in_library(music, path.format(lib=music))


def test_resolve_missing_raises(music):
    with pytest.raises(FileNotFoundError):
        library_edit.resolve_in_library(music, 'Missing')


def test_rename_folder(music):
    new = library_edit.rename_entry(os.path.join(music, 'Conni'), 'Conni Folge 1')
    assert new == os.path.join(music, 'Conni Folge 1')
    assert os.path.isfile(os.path.join(new, '01.mp3'))


@pytest.mark.parametrize('name', ['Intro', 'Intro.mp3', 'Intro.MP3'])
def test_rename_file_keeps_extension(music, name):
    new = library_edit.rename_entry(os.path.join(music, 'Conni', '01.mp3'), name)
    assert os.path.basename(new) == 'Intro.mp3'
    assert os.path.isfile(new)


def test_rename_to_existing_name_raises(music):
    with pytest.raises(FileExistsError):
        library_edit.rename_entry(os.path.join(music, 'Conni'), 'Other')


def test_rename_only_case(music):
    new = library_edit.rename_entry(os.path.join(music, 'Conni'), 'CONNI')
    assert os.listdir(music).count('CONNI') == 1
    assert 'Conni' not in os.listdir(music)
    assert new == os.path.join(music, 'CONNI')


def test_rename_cannot_leave_folder(music):
    new = library_edit.rename_entry(os.path.join(music, 'Conni', 'CD 1'), '../../x')
    assert os.path.dirname(new) == os.path.join(music, 'Conni')


LIB = '/music'


@pytest.mark.parametrize('value, expected', [
    ('/music/Conni', '/music/Conni 1'),
    ('/music/Conni/', '/music/Conni 1'),
    ('/music/Conni/01.mp3', '/music/Conni 1/01.mp3'),
    ('Conni', 'Conni 1'),
    ('Conni/CD/01.mp3', 'Conni 1/CD/01.mp3'),
    ('/music/ConniPlus', None),
    ('ConniPlus/01.mp3', None),
    ('/music', None),
    ('Other', None),
    ('http://example.com/Conni', None),
    ('', None),
    (None, None),
    (5, None),
])
def test_rewrite_path(value, expected):
    if sys.platform.startswith('win'):
        pytest.skip('POSIX paths')
    assert library_edit.rewrite_path(value, '/music/Conni', '/music/Conni 1', LIB) == expected


# ---------------------------------------------------------------------------
# PlayerMPD.rename
# ---------------------------------------------------------------------------

@pytest.fixture
def player(monkeypatch, music):
    p = playermpd.PlayerMPD.__new__(playermpd.PlayerMPD)
    p.mpd_client = mock.Mock()
    p.mpd_client.playlistinfo.return_value = []
    p.mpd_client.status.return_value = {'state': 'stop'}
    p.mpd_client.find.return_value = [{'file': 'Conni/01.mp3', 'title': 'Old'}]
    p.mpd_lock = threading.RLock()
    p.mpd_retry_with_mutex = lambda func, *args: func(*args)
    p.update = mock.Mock()
    status = {
        'player_status': {'last_played_folder': os.path.join(music, 'Conni'), 'CURRENTFILENAME': 'Conni/01.mp3'},
        'audio_folder_status': {
            os.path.join(music, 'Conni'): {'CURRENTFILENAME': 'Conni/01.mp3'},
            os.path.join(music, 'Other'): {'CURRENTFILENAME': 'Other/02.mp3'},
        },
    }
    p.music_player_status = mock.MagicMock()
    p.music_player_status.__getitem__.side_effect = status.__getitem__
    p.status = status
    monkeypatch.setattr(playermpd.components.player, 'get_music_library_path', lambda: music)
    calls = []
    monkeypatch.setattr(plugs, 'call_ignore_errors', lambda *args, **kwargs: calls.append((args, kwargs)))
    p.plugs_calls = calls
    return p


def test_rename_folder_adapts_status_and_cards(player, music):
    old, new = os.path.join(music, 'Conni'), os.path.join(music, 'Conni Neu')

    assert player.rename('Conni', 'Conni Neu') == new

    assert os.path.isdir(new)
    assert player.status['player_status'] == {'last_played_folder': new, 'CURRENTFILENAME': 'Conni Neu/01.mp3'}
    assert player.status['audio_folder_status'] == {
        new: {'CURRENTFILENAME': 'Conni Neu/01.mp3'},
        os.path.join(music, 'Other'): {'CURRENTFILENAME': 'Other/02.mp3'},
    }
    player.music_player_status.save_to_json.assert_called_once()
    assert player.plugs_calls == [(('cards', 'rewrite_paths'), {'args': [old, new, music]})]
    player.update.assert_called_once()


def test_rename_refused_while_playing(player, music):
    player.mpd_client.playlistinfo.return_value = [{'file': 'Conni/01.mp3'}]
    player.mpd_client.status.return_value = {'state': 'pause'}

    with pytest.raises(ValueError):
        player.rename('Conni', 'Conni Neu')

    assert os.path.isdir(os.path.join(music, 'Conni'))
    assert player.plugs_calls == []


def test_rename_stopped_clears_stale_queue(player, music):
    player.mpd_client.playlistinfo.return_value = [{'file': 'Conni/01.mp3'}]

    player.rename('Conni', 'Conni Neu')

    player.mpd_client.clear.assert_called_once()


def test_rename_other_queue_is_kept(player, music):
    player.mpd_client.playlistinfo.return_value = [{'file': 'Other/02.mp3'}]
    player.mpd_client.status.return_value = {'state': 'play'}

    player.rename('Conni', 'Conni Neu')

    player.mpd_client.clear.assert_not_called()


def test_rename_song_with_title(player, music, monkeypatch):
    set_title = mock.Mock()
    monkeypatch.setattr(library_edit, 'set_title', set_title)

    new = player.rename(os.path.join(music, 'Conni', '01.mp3'), 'Intro', title=' New ')

    assert new == os.path.join(music, 'Conni', 'Intro.mp3')
    set_title.assert_called_once_with(os.path.join(music, 'Conni', '01.mp3'), 'New')


def test_rename_unchanged_does_nothing(player, music, monkeypatch):
    set_title = mock.Mock()
    monkeypatch.setattr(library_edit, 'set_title', set_title)

    assert player.rename('Conni/01.mp3', '01', title='Old') == os.path.join(music, 'Conni', '01.mp3')

    set_title.assert_not_called()
    player.update.assert_not_called()
    player.music_player_status.save_to_json.assert_not_called()
