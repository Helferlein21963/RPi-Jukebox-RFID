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


# ---------------------------------------------------------------------------
# Order of a folder: library_edit and PlayerMPD.get_order_info / reorder
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('name, number, title', [
    ('07 - Alt', 7, 'Alt'),
    ('07_Alt', 7, 'Alt'),
    ('3. Alt', 3, 'Alt'),
    ('Alt 2', None, 'Alt 2'),
    ('2024', 2024, '2024'),
])
def test_track_number_and_strip_number(name, number, title):
    assert library_edit.track_number(name) == number
    assert library_edit.strip_number(name) == title


def test_reorder_names():
    assert library_edit.reorder_names(['Zebra.mp3', '07 - Alt.ogg', '01 - Anfang.mp3']) == [
        '01 - Zebra.mp3', '02 - Alt.ogg', '03 - Anfang.mp3']
    assert library_edit.reorder_names([f'{n}.mp3' for n in 'abcdefghijk'])[-1] == '11 - k.mp3'
    # Wide enough for the number of files
    assert library_edit.reorder_names(['x.mp3'] * 100)[0] == '001 - x.mp3'
    assert library_edit.reorder_names(['07 - ?.mp3']) == ['01 - Track.mp3']


def test_rename_files_swaps_names(tmp_path):
    (tmp_path / 'a.mp3').write_text('a')
    (tmp_path / 'b.mp3').write_text('b')
    (tmp_path / 'c.mp3').write_text('c')

    library_edit.rename_files(str(tmp_path), [('a.mp3', 'b.mp3'), ('b.mp3', 'a.mp3'), ('c.mp3', 'c.mp3')])

    assert (tmp_path / 'b.mp3').read_text() == 'a'
    assert (tmp_path / 'a.mp3').read_text() == 'b'
    assert sorted(os.listdir(tmp_path)) == ['a.mp3', 'b.mp3', 'c.mp3']


def test_rename_files_refuses_a_taken_name(tmp_path):
    (tmp_path / 'a.mp3').write_text('a')
    (tmp_path / '01 - a.mp3').write_text('other')

    with pytest.raises(FileExistsError):
        library_edit.rename_files(str(tmp_path), [('a.mp3', '01 - a.mp3')])

    assert (tmp_path / 'a.mp3').read_text() == 'a'


def test_rename_files_restores_names_on_error(tmp_path, monkeypatch):
    (tmp_path / 'a.mp3').write_text('a')
    (tmp_path / 'b.mp3').write_text('b')
    real_rename = os.rename

    def failing_rename(src, dst):
        if dst.endswith('02 - b.mp3'):
            raise OSError('disk full')
        real_rename(src, dst)

    monkeypatch.setattr(os, 'rename', failing_rename)
    with pytest.raises(OSError):
        library_edit.rename_files(str(tmp_path), [('a.mp3', '01 - a.mp3'), ('b.mp3', '02 - b.mp3')])

    assert sorted(os.listdir(tmp_path)) == ['a.mp3', 'b.mp3']
    assert (tmp_path / 'b.mp3').read_text() == 'b'


def test_set_track_number_keeps_the_date_order(tmp_path):
    pytest.importorskip('mutagen')
    from mutagen.id3 import ID3

    path = tmp_path / 'a.mp3'
    path.write_bytes(b'')
    os.utime(path, (1000, 1000))

    assert library_edit.set_track_number(str(path), 3, 12) is True

    assert str(ID3(str(path))['TRCK']) == '3/12'
    assert os.stat(path).st_mtime == 1001


@pytest.fixture
def maus(music):
    folder = os.path.join(music, 'Maus')
    os.mkdir(folder)
    for idx, name in enumerate(['01 - Aufsteigen.mp3', 'Hocke.mp3', 'cover.jpg', 'notes.txt']):
        with open(os.path.join(folder, name), 'w') as f:
            f.write(name)
        os.utime(os.path.join(folder, name), (1000 + idx, 1000 + idx))
    return folder


@pytest.fixture
def no_tags(monkeypatch):
    set_track_number = mock.Mock(return_value=True)
    monkeypatch.setattr(library_edit, 'set_track_number', set_track_number)
    return set_track_number


def test_get_order_info(player, maus):
    player.mpd_client.lsinfo.return_value = [
        {'directory': 'Maus/sub'},
        {'file': 'Maus/Hocke.mp3', 'title': ['In der Hocke', 'x'], 'track': '2/5'},
    ]

    assert player.get_order_info('Maus') == [
        {'file': '01 - Aufsteigen.mp3', 'title': '', 'track': None, 'modified': 1000},
        {'file': 'Hocke.mp3', 'title': 'In der Hocke', 'track': 2, 'modified': 1001},
    ]
    player.mpd_client.lsinfo.assert_called_once_with('Maus')


def test_get_order_info_refuses_playlist_folders(player, maus):
    open(os.path.join(maus, 'list.m3u'), 'w').close()

    with pytest.raises(ValueError):
        player.get_order_info('Maus')


def test_reorder_renames_and_adapts_status_and_cards(player, maus, music, no_tags):
    player.status['audio_folder_status'][maus] = {'CURRENTFILENAME': 'Maus/Hocke.mp3'}

    assert player.reorder('Maus', ['Hocke.mp3', '01 - Aufsteigen.mp3']) == ['01 - Hocke.mp3', '02 - Aufsteigen.mp3']

    assert sorted(os.listdir(maus)) == ['01 - Hocke.mp3', '02 - Aufsteigen.mp3', 'cover.jpg', 'notes.txt']
    with open(os.path.join(maus, '01 - Hocke.mp3')) as f:
        assert f.read() == 'Hocke.mp3'
    assert player.status['audio_folder_status'][maus] == {'CURRENTFILENAME': 'Maus/01 - Hocke.mp3'}
    assert no_tags.call_args_list == [
        mock.call(os.path.join(maus, '01 - Hocke.mp3'), 1, 2),
        mock.call(os.path.join(maus, '02 - Aufsteigen.mp3'), 2, 2),
    ]
    assert player.plugs_calls == [(('cards', 'rewrite_paths_many'), {'args': [[
        [os.path.join(maus, 'Hocke.mp3'), os.path.join(maus, '01 - Hocke.mp3')],
        [os.path.join(maus, '01 - Aufsteigen.mp3'), os.path.join(maus, '02 - Aufsteigen.mp3')],
    ], music]})]
    player.update.assert_called_once()


def test_reorder_refused_while_playing(player, maus, no_tags):
    player.mpd_client.playlistinfo.return_value = [{'file': 'Maus/Hocke.mp3'}]
    player.mpd_client.status.return_value = {'state': 'play'}

    with pytest.raises(ValueError):
        player.reorder('Maus', ['Hocke.mp3', '01 - Aufsteigen.mp3'])

    assert 'Hocke.mp3' in os.listdir(maus)
    assert player.plugs_calls == []


@pytest.mark.parametrize('files', [
    ['Hocke.mp3'],
    ['Hocke.mp3', 'Hocke.mp3'],
    ['Hocke.mp3', '01 - Aufsteigen.mp3', 'cover.jpg'],
    ['Hocke.mp3', '../Conni/01.mp3'],
])
def test_reorder_refuses_other_files(player, maus, no_tags, files):
    with pytest.raises(ValueError):
        player.reorder('Maus', files)

    assert 'Hocke.mp3' in os.listdir(maus)


def test_get_folder_content_has_dates(player, maus):
    content = player.get_folder_content('Maus')

    assert [(entry['name'], entry['modified']) for entry in content] == [
        ('01 - Aufsteigen.mp3', 1000), ('Hocke.mp3', 1001)]
