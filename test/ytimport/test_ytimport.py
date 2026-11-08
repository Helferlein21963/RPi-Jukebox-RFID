# RPi-Jukebox-RFID Version 3
# Copyright (c) See file LICENSE in project root folder
"""Tests for the YouTube import (ytimport): name cleaning, metadata, track list, import job (no network)"""
import io
import os
import sys
import threading
from unittest import mock

import pytest

# In case this is run locally from
sys.path.append(os.path.abspath('../../src/jukebox'))
import jukebox.plugs as plugs  # noqa: E402

plugs.ALLOW_DIRECT_IMPORTS = True
import components.ytimport as ytimport  # noqa: E402
from components.ytimport import utils  # noqa: E402


# ---------------------------------------------------------------------------
# utils
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('name, expected', [
    ('Max übernachtet bei Oma', 'Max_uebernachtet_bei_Oma'),
    ('ÄÖÜ äöü ß', 'AeOeUe_aeoeue_ss'),
    ('  Die drei ??? - Folge 1  ', 'Die_drei_Folge_1'),
    ('Max & Co. (Folge 12)', 'Max_Co_Folge_12'),
    ('../../etc/passwd', 'etc_passwd'),
    ('already__clean-name', 'already_clean_name'),
    ('Already_Clean', 'Already_Clean'),
    ('🎵🎵', ''),
    ('', ''),
    (None, ''),
])
def test_sanitize_folder(name, expected):
    assert utils.sanitize_folder(name) == expected


def test_sanitize_folder_is_limited():
    assert len(utils.sanitize_folder('word ' * 50)) <= utils.FOLDER_MAX_LENGTH


@pytest.mark.parametrize('title, expected', [
    ('Kapitel 1: Der Anfang', 'Kapitel 1 Der Anfang'),
    ('AC/DC - Thunder?', 'AC DC - Thunder'),
    ('Über "Größe"', 'Über Größe'),
    ('...', 'Track'),
    ('', 'Track'),
])
def test_safe_filename(title, expected):
    assert utils.safe_filename(title) == expected


def test_track_filename_sorts_by_number():
    names = [utils.track_filename(n, 'x', width=3) for n in (10, 2, 100)]
    assert names == ['010 - x.mp3', '002 - x.mp3', '100 - x.mp3']
    assert sorted(names) == ['002 - x.mp3', '010 - x.mp3', '100 - x.mp3']


def test_clean_artist():
    assert utils.clean_artist('Some Artist - Topic') == 'Some Artist'
    assert utils.clean_artist('Kanal') == 'Kanal'
    assert utils.clean_artist(None) == ''


def test_build_info_video_with_chapters():
    raw = {
        'title': 'Max übernachtet bei Oma', 'uploader': 'Erzähler - Topic', 'duration': 300,
        'webpage_url': 'https://www.youtube.com/watch?v=abc', 'thumbnail': 'https://i.ytimg.com/abc.jpg',
        'chapters': [
            {'title': 'Teil 1', 'start_time': 0, 'end_time': 100},
            {'title': '', 'start_time': 100},
            {'title': 'Leer', 'start_time': 250, 'end_time': 250},
            {'title': 'Ende', 'start_time': 250},
        ],
    }
    info = utils.build_info(raw, 'https://youtu.be/abc', 200)

    assert info['kind'] == 'video'
    assert info['folder'] == 'Max_uebernachtet_bei_Oma'
    assert info['uploader'] == 'Erzähler'
    assert info['thumbnail'] == 'https://i.ytimg.com/abc.jpg'
    assert len(info['entries']) == 1
    entry = info['entries'][0]
    assert entry['url'] == 'https://www.youtube.com/watch?v=abc'
    assert entry['chapters'] == [
        {'title': 'Teil 1', 'start': 0.0, 'end': 100.0},
        {'title': 'Kapitel 2', 'start': 100.0, 'end': 250.0},
        {'title': 'Ende', 'start': 250.0, 'end': 300.0},
    ]


def test_build_info_playlist():
    def entries():
        yield {'id': 'a', 'title': 'Song A', 'duration': 60, 'ie_key': 'Youtube'}
        yield None
        yield {'url': 'https://www.youtube.com/watch?v=b', 'title': '[Private video]'}
        yield {'title': 'no link', 'ie_key': 'Other'}
        yield {'id': 'c', 'title': 'Song C'}

    raw = {'_type': 'playlist', 'title': 'Meine Liste', 'channel': 'Kanal', 'entries': entries(),
           'thumbnails': [{'url': 'small'}, {'url': 'large'}]}
    info = utils.build_info(raw, 'https://www.youtube.com/playlist?list=x', 200)

    assert info['kind'] == 'playlist'
    assert info['uploader'] == 'Kanal'
    assert info['thumbnail'] == 'large'
    assert info['truncated'] is False
    assert [(e['url'], e['title'], e['available']) for e in info['entries']] == [
        ('https://www.youtube.com/watch?v=a', 'Song A', True),
        ('https://www.youtube.com/watch?v=b', '[Private video]', False),
        ('https://www.youtube.com/watch?v=c', 'Song C', True),
    ]


def test_build_info_playlist_is_limited():
    raw = {'_type': 'playlist', 'title': 'Mix', 'entries': ({'id': str(n), 'title': str(n)} for n in range(1000))}
    info = utils.build_info(raw, 'https://x', 5)
    assert len(info['entries']) == 5
    assert info['truncated'] is True


def test_build_info_podcast_feed():
    # As yt-dlp's generic extractor lists an RSS feed: no channel author or image, data per episode
    raw = {'_type': 'playlist', 'extractor': 'generic', 'title': 'Hörspiel-Podcast', 'entries': [
        {'_type': 'url_transparent', 'url': 'https://cdn.example/2.mp3#__youtubedl_smuggle=x', 'title': 'Folge 2',
         'timestamp': 1794114031, 'duration': 3606, 'thumbnail': 'https://cdn.example/episode.jpg'},
        {'_type': 'url_transparent', 'url': 'https://cdn.example/1.mp3', 'title': 'Folge 1', 'timestamp': None},
    ]}
    info = utils.build_info(raw, 'https://example/feed.rss', 200)

    assert info['kind'] == 'feed'
    assert info['uploader'] == 'Hörspiel-Podcast'
    assert info['thumbnail'] == 'https://cdn.example/episode.jpg'
    assert info['folder'] == 'Hoerspiel_Podcast'
    # Order as in the feed (newest first)
    assert [(e['title'], e['date'], e['duration']) for e in info['entries']] == [
        ('Folge 2', '2026-11-08', 3606), ('Folge 1', None, None)]
    assert info['entries'][0]['url'].startswith('https://cdn.example/2.mp3')


def test_build_info_direct_file():
    raw = {'title': 'ef1f11de_MP3-128', 'direct': True, 'extractor': 'generic', 'timestamp': 1793703189,
           'webpage_url': 'https://cdn.example/ef1f11de_MP3-128.mp3'}
    info = utils.build_info(raw, 'https://cdn.example/ef1f11de_MP3-128.mp3', 200)
    assert info['kind'] == 'video'
    assert info['entries'][0]['date'] == '2026-11-03'
    assert info['entries'][0]['chapters'] == []


def test_normalize_tracks():
    tracks = utils.normalize_tracks([
        {'url': 'https://y/1', 'title': '  Titel   eins '},
        {'url': 'https://y/2', 'title': '', 'start': 10, 'end': '20.5'},
        {'url': 'https://y/2', 'title': 'x', 'start': '', 'end': None},
    ])
    assert tracks == [
        {'url': 'https://y/1', 'title': 'Titel eins', 'start': None, 'end': None},
        {'url': 'https://y/2', 'title': 'Track', 'start': 10.0, 'end': 20.5},
        {'url': 'https://y/2', 'title': 'x', 'start': None, 'end': None},
    ]


@pytest.mark.parametrize('tracks', [
    'not a list',
    [{'url': 'file:///etc/passwd', 'title': 'x'}],
    [{'url': 'https://y', 'title': 'x', 'start': 20, 'end': 10}],
    [{'url': 'https://y', 'title': 'x', 'start': -1}],
    ['https://y'],
])
def test_normalize_tracks_rejects(tracks):
    with pytest.raises(ValueError):
        utils.normalize_tracks(tracks)


def test_ffmpeg_convert_cmd():
    cmd = utils.ffmpeg_convert_cmd('ffmpeg', 'in.webm', 'out.mp3', 2)
    assert '-ss' not in cmd and '-t' not in cmd
    assert cmd[cmd.index('-q:a') + 1] == '2'
    assert cmd[-1] == 'out.mp3'

    cmd = utils.ffmpeg_convert_cmd('ffmpeg', 'in.webm', 'out.mp3', 4, start=100, end=250.5)
    assert cmd[cmd.index('-ss') + 1] == '100.000'
    assert cmd[cmd.index('-t') + 1] == '150.500'
    # Seek before the input (fast), duration after it
    assert cmd.index('-ss') < cmd.index('-i') < cmd.index('-t')


def test_ffmpeg_convert_cmd_copies_mp3():
    cmd = utils.ffmpeg_convert_cmd('ffmpeg', 'in.mp3', 'out.mp3', 2, start=10, end=20, copy=True)
    assert cmd[cmd.index('-codec:a') + 1] == 'copy'
    assert 'libmp3lame' not in cmd and '-q:a' not in cmd
    # Cover (video stream) and tags of the source are dropped, cutting still works
    assert '-vn' in cmd and cmd[cmd.index('-map_metadata') + 1] == '-1'
    assert cmd[cmd.index('-t') + 1] == '10.000'


def test_parse_ffmpeg_progress():
    assert utils.parse_ffmpeg_progress('out_time_us=1500000\n') == 1.5
    assert utils.parse_ffmpeg_progress('out_time_ms=2000000') == 2.0
    assert utils.parse_ffmpeg_progress('out_time_us=N/A') is None
    assert utils.parse_ffmpeg_progress('progress=continue') is None


def test_tag_mp3(tmp_path):
    id3 = pytest.importorskip('mutagen.id3')
    path = tmp_path / 'song.mp3'
    path.write_bytes(b'\xff\xfb\x90\x00' + bytes(1000))

    utils.tag_mp3(str(path), 'Titel ä', 'Künstler', 'Album', 3, 12, b'jpegdata')

    tags = id3.ID3(str(path))
    assert tags['TIT2'].text == ['Titel ä']
    assert tags['TPE1'].text == ['Künstler']
    assert tags['TPE2'].text == ['Künstler']
    assert tags['TALB'].text == ['Album']
    assert tags['TRCK'].text == ['3/12']
    assert tags.getall('APIC')[0].data == b'jpegdata'
    assert tags.version[:2] == (2, 3)


def make_tagged_mp3(path, title='Folge 1 | Podcast', artist='', album='Podcast', cover=b'picture'):
    pytest.importorskip('mutagen.id3')
    path.write_bytes(b'\xff\xfb\x90\x00' + bytes(1000))
    utils.tag_mp3(str(path), title, artist, album, cover=cover)
    return path.read_bytes()


def test_id3_tag_size_and_summary(tmp_path):
    data = make_tagged_mp3(tmp_path / 'episode.mp3', title='Aufsteigen  | Die Maus')
    size = utils.id3_tag_size(data[:10])
    # The tag ends where the audio starts
    assert data[size:size + 2] == b'\xff\xfb'
    assert utils.id3_summary(data[:size]) == {'title': 'Aufsteigen | Die Maus', 'artist': '', 'album': 'Podcast'}

    assert utils.id3_tag_size(b'\xff\xfb\x90\x00' + bytes(10)) is None
    assert utils.id3_tag_size(b'ID3') is None
    assert utils.id3_summary(b'no tag at all') == {'title': '', 'artist': '', 'album': ''}
    # Cut off in the middle of the tag
    assert utils.id3_summary(data[:size // 2]) == {'title': '', 'artist': '', 'album': ''}


@pytest.mark.parametrize('name, number, title', [
    ('07 - Titel.mp3', 7, 'Titel.mp3'),
    ('007_Titel.mp3', 7, 'Titel.mp3'),
    ('3. Titel', 3, 'Titel'),
    ('12 Titel', 12, 'Titel'),
    ('Titel 2', None, 'Titel 2'),
    ('1984', 1984, '1984'),
])
def test_track_number_and_strip_number(name, number, title):
    assert utils.track_number(name) == number
    assert utils.strip_number(name) == title


def test_plan_append_names_numbered():
    names, numbered = utils.plan_append_names(['01 - A.mp3', '02 - B.mp3'], ['Neu', 'Noch neu'])
    assert numbered is True
    assert names == ['03 - Neu.mp3', '04 - Noch neu.mp3']
    # Keeps a wider numbering, widens when needed
    assert utils.plan_append_names(['001 A.mp3'], ['Neu'])[0] == ['002 - Neu.mp3']
    assert utils.plan_append_names(['99 - A.mp3'], ['Neu'])[0] == ['100 - Neu.mp3']
    # An empty folder starts at 01
    assert utils.plan_append_names([], ['Neu']) == (['01 - Neu.mp3'], True)


def test_plan_append_names_not_numbered():
    names, numbered = utils.plan_append_names(['01 - A.mp3', 'Lied.mp3'], ['Neu', 'lied', 'Lied'])
    assert numbered is False
    # Sorted in alphabetically, never the name of an existing file
    assert names == ['Neu.mp3', 'lied (2).mp3', 'Lied (3).mp3']


def test_plan_reorder_names():
    names = utils.plan_reorder_names([{'file': 'Lied B.mp3'}, {'title': 'Neu'}, {'file': '03 - Lied A.ogg'},
                                      {'file': '04 - Lied A.mp3'}])
    assert names == ['01 - Lied B.mp3', '02 - Neu.mp3', '03 - Lied A.ogg', '04 - Lied A.mp3']


def test_normalize_tracks_with_existing_files():
    tracks = [{'file': 'Lied.mp3'}, {'url': 'https://y/1', 'title': 'Neu'}]
    assert utils.normalize_tracks(tracks, allow_existing=True) == [
        {'file': 'Lied.mp3'}, {'url': 'https://y/1', 'title': 'Neu', 'start': None, 'end': None}]
    with pytest.raises(ValueError):
        utils.normalize_tracks(tracks)
    for name in ('../Lied.mp3', 'a/Lied.mp3', '..', 'a\\b.mp3'):
        with pytest.raises(ValueError):
            utils.normalize_tracks([{'file': name}], allow_existing=True)


def test_set_track_number(tmp_path):
    id3 = pytest.importorskip('mutagen.id3')
    make_tagged_mp3(tmp_path / 'tagged.mp3', title='Lied')
    utils.set_track_number(str(tmp_path / 'tagged.mp3'), 3, 12)
    tags = id3.ID3(str(tmp_path / 'tagged.mp3'))
    assert tags['TRCK'].text == ['3/12']
    assert tags['TIT2'].text == ['Lied']
    assert tags.version[:2] == (2, 3)

    (tmp_path / 'untagged.mp3').write_bytes(b'\xff\xfb\x90\x00' + bytes(100))
    utils.set_track_number(str(tmp_path / 'untagged.mp3'), 1, 2)
    assert id3.ID3(str(tmp_path / 'untagged.mp3'))['TRCK'].text == ['1/2']


def test_embedded_cover(tmp_path):
    make_tagged_mp3(tmp_path / 'with.mp3', cover=b'picture')
    make_tagged_mp3(tmp_path / 'without.mp3', cover=None)
    (tmp_path / 'untagged.mp3').write_bytes(b'\xff\xfb\x90\x00' + bytes(100))

    assert utils.embedded_cover(str(tmp_path / 'with.mp3')) == b'picture'
    assert utils.embedded_cover(str(tmp_path / 'without.mp3')) is None
    assert utils.embedded_cover(str(tmp_path / 'untagged.mp3')) is None


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------

@pytest.fixture
def library(tmp_path):
    lib = tmp_path / 'audiofolders'
    lib.mkdir()
    return lib


@pytest.fixture
def ctrl(tmp_path, library):
    c = ytimport.YtImport.__new__(ytimport.YtImport)
    c._quality = 2
    c._js_runtime = 'node'
    c._js_runtime_path = None
    c._nice = 0
    c._max_entries = 200
    c._tmp_base = str(tmp_path / 'tmp')
    c._ffmpeg = 'ffmpeg'
    c._lock = threading.RLock()
    c._thread = None
    c._cancel = threading.Event()
    c._proc = None
    c._status = {'state': 'idle'}
    c._last_publish = 0.0
    c._versions = None
    c._last_info = None
    c.published = []
    c._publish = lambda force=False: c.published.append(dict(c._status))
    with mock.patch.object(ytimport.components.player, 'get_music_library_path', return_value=str(library)), \
            mock.patch.object(ytimport.plugs, 'call_ignore_errors') as call, \
            mock.patch.object(ytimport.misc, 'recursive_chmod'):
        c.plugs_call = call
        yield c


def wait(ctrl):
    ctrl._thread.join(timeout=10)
    assert not ctrl._thread.is_alive()


def fake_download(ctrl, fail_urls=()):
    """Replace the download: writes a source file, fails for ``fail_urls``"""
    downloads = []

    def download(url, src_dir, number, cover):
        downloads.append(url)
        if url in fail_urls:
            raise RuntimeError('Video unavailable')
        audio = os.path.join(src_dir, f'{number:04d}.webm')
        with open(audio, 'wb') as f:
            f.write(b'audio')
        return {'audio': audio, 'cover': b'cover' if cover else None, 'duration': 100}

    ctrl._download = download
    return downloads


def fake_convert(ctrl):
    calls = []

    def convert(source, destination, start, end):
        calls.append((os.path.basename(destination), start, end))
        with open(destination, 'wb') as f:
            f.write(b'mp3')

    ctrl._convert = convert
    return calls


def test_folder_info_new(ctrl, library):
    assert ctrl.folder_info('Neuer Ordner') == {'folder': 'Neuer_Ordner', 'exists': False}
    assert ctrl.folder_info('???') == {'folder': '', 'exists': False}
    # Never outside of the library
    assert ctrl.folder_info('../audiofolders') == {'folder': 'audiofolders', 'exists': False}


def test_folder_info_existing(ctrl, library):
    folder = library / 'Max_uebernachtet'
    folder.mkdir()
    make_tagged_mp3(folder / 'b Lied.mp3', title='Lied', artist='Erzähler', album='Max')
    (folder / '02 - Anfang.mp3').write_bytes(b'mp3')
    (folder / 'cover.jpg').write_bytes(b'jpg')

    info = ctrl.folder_info('Max übernachtet')
    assert info == {
        'folder': 'Max_uebernachtet', 'exists': True, 'numbered': False, 'artist': 'Erzähler', 'album': 'Max',
        # In the order the player plays them
        'tracks': [{'file': '02 - Anfang.mp3', 'title': 'Anfang'}, {'file': 'b Lied.mp3', 'title': 'b Lied'}],
    }
    (folder / 'b Lied.mp3').rename(folder / '01 - Lied.mp3')
    assert ctrl.folder_info('Max_uebernachtet')['numbered'] is True


def test_list_folders(ctrl, library):
    (library / 'b_Hoerspiel').mkdir()
    (library / 'b_Hoerspiel' / '01.mp3').write_bytes(b'mp3')
    (library / 'b_Hoerspiel' / 'cover.jpg').write_bytes(b'jpg')
    (library / 'A_Lieder' / 'CD 1').mkdir(parents=True)
    (library / '.hidden').mkdir()
    assert ctrl.list_folders() == [
        {'folder': 'A_Lieder', 'tracks': 0},
        {'folder': 'A_Lieder/CD 1', 'tracks': 0},
        {'folder': 'b_Hoerspiel', 'tracks': 1},
    ]


def test_start_import_validates(ctrl, library):
    (library / 'Max').mkdir()
    with pytest.raises(FileExistsError):
        ctrl.start_import('Max', [{'url': 'https://y/1', 'title': 'a'}])
    with pytest.raises(ValueError):
        ctrl.start_import('???', [{'url': 'https://y/1', 'title': 'a'}])
    with pytest.raises(ValueError):
        ctrl.start_import('Neu', [])
    assert ctrl._thread is None


def test_import_chapters_and_tracks(ctrl, library):
    downloads = fake_download(ctrl)
    converts = fake_convert(ctrl)
    tracks = [
        {'url': 'https://y/book', 'title': 'Kapitel 1', 'start': 0, 'end': 50},
        {'url': 'https://y/song', 'title': 'Lied'},
        {'url': 'https://y/book', 'title': 'Kapitel 2', 'start': 50, 'end': 100},
    ]
    with mock.patch.object(utils, 'tag_mp3') as tag:
        folder = ctrl.start_import('Mein Hörspiel', tracks, artist='Ich', album='Album')
        wait(ctrl)

    assert folder == 'Mein_Hoerspiel'
    # Each video is downloaded only once, also when several chapters are cut out of it
    assert downloads == ['https://y/book', 'https://y/song']
    assert converts == [('0001.mp3', 0.0, 50.0), ('0002.mp3', None, None), ('0003.mp3', 50.0, 100.0)]
    assert sorted(os.listdir(library / 'Mein_Hoerspiel')) == ['01 - Kapitel 1.mp3', '02 - Lied.mp3',
                                                              '03 - Kapitel 2.mp3']
    # Tagged in the working directory, before the folder is moved into the library
    assert tag.call_args_list[1] == mock.call(mock.ANY, 'Lied', 'Ich', 'Album', 2, 3, b'cover')
    assert os.path.basename(tag.call_args_list[1][0][0]) == '02 - Lied.mp3'
    assert ctrl._status['state'] == 'done'
    assert ctrl._status['folder'] == 'Mein_Hoerspiel'
    assert ctrl._status['imported'] == 3
    ctrl.plugs_call.assert_called_once_with('player', 'ctrl', 'update')
    # The working directory is cleaned up
    assert os.listdir(ctrl._tmp_base) == []
    states = [s['state'] for s in ctrl.published]
    assert states[0] == 'importing' and states[-1] == 'done'


def test_import_skips_failed_tracks(ctrl, library):
    fake_download(ctrl, fail_urls=['https://y/2'])
    fake_convert(ctrl)
    with mock.patch.object(utils, 'tag_mp3'):
        ctrl.start_import('Liste', [{'url': 'https://y/1', 'title': 'a'}, {'url': 'https://y/2', 'title': 'b'}],
                          cover=False)
        wait(ctrl)

    assert ctrl._status['state'] == 'done'
    assert ctrl._status['imported'] == 1
    assert ctrl._status['failed'] == [{'title': 'b', 'error': 'Video unavailable'}]
    assert os.listdir(library / 'Liste') == ['01 - a.mp3']


def test_import_all_failed(ctrl, library):
    fake_download(ctrl, fail_urls=['https://y/1'])
    fake_convert(ctrl)
    ctrl.start_import('Liste', [{'url': 'https://y/1', 'title': 'a'}])
    wait(ctrl)

    assert ctrl._status['state'] == 'error'
    assert 'Video unavailable' in ctrl._status['error']
    assert not (library / 'Liste').exists()
    ctrl.plugs_call.assert_not_called()


def test_import_cancel(ctrl, library):
    fake_download(ctrl)
    started = threading.Event()
    release = threading.Event()

    def convert(source, destination, start, end):
        started.set()
        release.wait(5)
        ctrl._check_cancel()

    ctrl._convert = convert
    ctrl.start_import('Liste', [{'url': 'https://y/1', 'title': 'a'}, {'url': 'https://y/2', 'title': 'b'}])
    assert started.wait(5)
    with pytest.raises(RuntimeError):
        ctrl.fetch_info('https://y/other')  # busy
    ctrl.cancel()
    release.set()
    wait(ctrl)

    assert ctrl._status['state'] == 'cancelled'
    assert not (library / 'Liste').exists()
    assert os.listdir(ctrl._tmp_base) == []


def test_fetch_info_follows_redirects(ctrl):
    ydl = mock.MagicMock()
    ydl.__enter__.return_value = ydl
    ydl.extract_info.side_effect = [
        {'_type': 'url', 'url': 'https://www.youtube.com/playlist?list=x'},
        {'_type': 'playlist', 'title': 'Liste', 'entries': [{'id': 'a', 'title': 'A'}]},
    ]
    fake_yt_dlp = mock.Mock()
    fake_yt_dlp.YoutubeDL.return_value = ydl
    with mock.patch.object(ytimport, '_import_yt_dlp', return_value=fake_yt_dlp):
        ctrl.fetch_info(' https://www.youtube.com/watch?v=a&list=x ')
        wait(ctrl)

    options = fake_yt_dlp.YoutubeDL.call_args[0][0]
    assert options['js_runtimes'] == {'node': {}}
    assert ydl.extract_info.call_args_list[1] == mock.call('https://www.youtube.com/playlist?list=x',
                                                           download=False, process=False)
    assert ctrl._status['state'] == 'info'
    assert ctrl._status['info']['title'] == 'Liste'
    assert ctrl._status['info']['entries'][0]['url'] == 'https://www.youtube.com/watch?v=a'


def test_fetch_info_error(ctrl):
    with pytest.raises(ValueError):
        ctrl.fetch_info('kein link')
    with mock.patch.object(ytimport, '_import_yt_dlp', side_effect=RuntimeError('yt-dlp is not installed')):
        ctrl.fetch_info('https://youtu.be/a')
        wait(ctrl)
    assert ctrl._status == {'state': 'error', 'error': 'yt-dlp is not installed', 'url': 'https://youtu.be/a'}


def test_reset(ctrl):
    ctrl._status = {'state': 'done', 'folder': 'x'}
    ctrl.reset()
    assert ctrl._status == {'state': 'idle'}


def test_get_versions(ctrl):
    versions = ctrl.get_versions()
    assert set(versions) == {'ytdlp', 'ytdlp_loaded', 'restart_required', 'ejs', 'mutagen', 'ffmpeg',
                             'js_runtime', 'js_runtime_version', 'js_runtime_supported', 'js_runtime_min'}
    assert versions['js_runtime'] == 'node'
    # Cached: checked only once
    with mock.patch.object(ctrl, '_check_versions') as check:
        ctrl.get_versions()
        check.assert_not_called()
        ctrl.get_versions(refresh=True)
        check.assert_called_once()


def fake_yt_dlp(*results):
    """yt-dlp module whose YoutubeDL().extract_info returns ``results`` one after another"""
    ydl = mock.MagicMock()
    ydl.__enter__.return_value = ydl
    ydl.extract_info.side_effect = list(results)
    module = mock.Mock()
    module.YoutubeDL.return_value = ydl
    return module


def test_fetch_info_direct_file_takes_the_file_tags(ctrl):
    raw = {'title': 'ef1f11de_MP3-128', 'direct': True, 'extractor': 'generic',
           'webpage_url': 'https://cdn.example/ef1f11de_MP3-128.mp3'}
    tags = {'title': 'Aufsteigen | Die Maus', 'artist': '', 'album': 'Die Maus zum Hören'}
    with mock.patch.object(ytimport, '_import_yt_dlp', return_value=fake_yt_dlp(raw)), \
            mock.patch.object(ytimport.YtImport, '_remote_id3', return_value=tags) as remote:
        ctrl.fetch_info('https://cdn.example/ef1f11de_MP3-128.mp3')
        wait(ctrl)

    remote.assert_called_once_with('https://cdn.example/ef1f11de_MP3-128.mp3')
    info = ctrl._status['info']
    assert info['entries'][0]['title'] == 'Aufsteigen | Die Maus'
    assert info['title'] == 'Die Maus zum Hören'
    assert info['uploader'] == 'Die Maus zum Hören'
    assert info['folder'] == 'Die_Maus_zum_Hoeren'


def test_fetch_info_direct_file_without_tags(ctrl):
    raw = {'title': 'ef1f11de_MP3-128', 'direct': True, 'extractor': 'generic',
           'webpage_url': 'https://cdn.example/ef1f11de_MP3-128.mp3'}
    with mock.patch.object(ytimport, '_import_yt_dlp', return_value=fake_yt_dlp(raw)), \
            mock.patch.object(ytimport.YtImport, '_remote_id3', side_effect=OSError('HTTP Error 403')):
        ctrl.fetch_info('https://cdn.example/ef1f11de_MP3-128.mp3')
        wait(ctrl)

    # The file name stays the title
    assert ctrl._status['state'] == 'info'
    assert ctrl._status['info']['entries'][0]['title'] == 'ef1f11de_MP3-128'


def test_remote_id3_loads_only_the_tag(tmp_path):
    data = make_tagged_mp3(tmp_path / 'episode.mp3') + bytes(5000)
    requested = []

    def urlopen(request, timeout):
        start, end = request.get_header('Range').removeprefix('bytes=').split('-')
        requested.append((int(start), int(end)))
        # A server that ignores the range: the whole file
        return io.BytesIO(data)

    with mock.patch.object(ytimport.urllib.request, 'urlopen', side_effect=urlopen):
        tags = ytimport.YtImport._remote_id3('https://cdn.example/episode.mp3')

    size = utils.id3_tag_size(data)
    assert requested == [(0, 9), (0, size - 1)]
    assert tags == {'title': 'Folge 1 | Podcast', 'artist': '', 'album': 'Podcast'}


def make_folder(library, name, files):
    folder = library / name
    folder.mkdir()
    for file in files:
        (folder / file).write_bytes(b'old ' + file.encode())
    return folder


def test_import_appends_to_numbered_folder(ctrl, library):
    folder = make_folder(library, 'Podcast', ['01 - Folge 1.mp3', '02 - Folge 2.mp3'])
    fake_download(ctrl)
    fake_convert(ctrl)
    with mock.patch.object(utils, 'tag_mp3') as tag:
        assert ctrl.start_import('Podcast', [{'url': 'https://y/3', 'title': 'Folge 3'}], artist='WDR',
                                 album='Podcast', target='existing') == 'Podcast'
        wait(ctrl)

    assert ctrl._status['state'] == 'done'
    assert ctrl._status['target'] == 'existing'
    assert sorted(os.listdir(folder)) == ['01 - Folge 1.mp3', '02 - Folge 2.mp3', '03 - Folge 3.mp3']
    # The old files are unchanged
    assert (folder / '01 - Folge 1.mp3').read_bytes() == b'old 01 - Folge 1.mp3'
    assert tag.call_args == mock.call(mock.ANY, 'Folge 3', 'WDR', 'Podcast', 3, None, b'cover')
    ctrl.plugs_call.assert_called_once_with('player', 'ctrl', 'update')


def test_import_sorts_into_unnumbered_folder(ctrl, library):
    folder = make_folder(library, 'Lieder', ['Zebra.mp3', '01 - Anfang.mp3'])
    fake_download(ctrl)
    fake_convert(ctrl)
    with mock.patch.object(utils, 'tag_mp3') as tag:
        ctrl.start_import('Lieder', [{'url': 'https://y/1', 'title': 'Affe'}], target='existing')
        wait(ctrl)

    assert sorted(os.listdir(folder)) == ['01 - Anfang.mp3', 'Affe.mp3', 'Zebra.mp3']
    assert tag.call_args == mock.call(mock.ANY, 'Affe', '', '', None, None, b'cover')


def test_import_with_new_order_renames_the_folder(ctrl, library):
    folder = make_folder(library, 'Lieder', ['Zebra.mp3', '01 - Anfang.mp3', 'cover.jpg'])
    fake_download(ctrl, fail_urls=['https://y/broken'])
    fake_convert(ctrl)
    tracks = [
        {'file': 'Zebra.mp3'},
        {'url': 'https://y/broken', 'title': 'Kaputt'},
        {'url': 'https://y/1', 'title': 'Affe'},
        # '01 - Anfang.mp3' is missing: it keeps its place at the end
    ]
    with mock.patch.object(utils, 'tag_mp3') as tag, \
            mock.patch.object(utils, 'set_track_number') as set_number, \
            mock.patch.object(ytimport.plugs, 'call', return_value=[{'file': 'Anderer/1.mp3'}]) as call:
        ctrl.start_import('Lieder', tracks, target='existing', reorder=True)
        wait(ctrl)
    # The old files get the track numbers of the new order
    assert set_number.call_args_list == [mock.call(str(folder / '01 - Zebra.mp3'), 1, 3),
                                         mock.call(str(folder / '03 - Anfang.mp3'), 3, 3)]

    assert ctrl._status['state'] == 'done'
    call.assert_called_once_with('player', 'ctrl', 'playlistinfo')
    # The failed track leaves no gap
    assert sorted(os.listdir(folder)) == ['01 - Zebra.mp3', '02 - Affe.mp3', '03 - Anfang.mp3', 'cover.jpg']
    assert (folder / '01 - Zebra.mp3').read_bytes() == b'old Zebra.mp3'
    assert (folder / '03 - Anfang.mp3').read_bytes() == b'old 01 - Anfang.mp3'
    assert tag.call_args == mock.call(mock.ANY, 'Affe', '', '', 2, 3, b'cover')


def test_import_with_new_order_refused_while_loaded(ctrl, library):
    folder = make_folder(library, 'Lieder', ['Zebra.mp3', 'Affe.mp3'])
    fake_download(ctrl)
    fake_convert(ctrl)
    tracks = [{'file': 'Zebra.mp3'}, {'file': 'Affe.mp3'}, {'url': 'https://y/1', 'title': 'Neu'}]
    with mock.patch.object(utils, 'tag_mp3'), \
            mock.patch.object(ytimport.plugs, 'call', return_value=[{'file': 'Lieder/Affe.mp3'}]):
        ctrl.start_import('Lieder', tracks, target='existing', reorder=True)
        wait(ctrl)

    assert ctrl._status['state'] == 'error'
    assert 'loaded in the player' in ctrl._status['error']
    assert sorted(os.listdir(folder)) == ['Affe.mp3', 'Zebra.mp3']
    assert os.listdir(ctrl._tmp_base) == []


def test_start_import_existing_validates(ctrl, library):
    make_folder(library, 'Lieder', ['Affe.mp3'])
    with pytest.raises(FileNotFoundError):
        ctrl.start_import('Gibt es nicht', [{'url': 'https://y/1', 'title': 'a'}], target='existing')
    with pytest.raises(ValueError):
        ctrl.start_import('Lieder', [{'file': 'Fremd.mp3'}, {'url': 'https://y/1', 'title': 'a'}],
                          target='existing', reorder=True)
    with pytest.raises(ValueError):
        ctrl.start_import('Lieder', [{'file': 'Affe.mp3'}], target='existing', reorder=True)
    with pytest.raises(ValueError):
        ctrl.start_import('Lieder', [{'url': 'https://y/1', 'title': 'a'}], target='irgendwo')
    assert ctrl._thread is None


def test_reopen_after_import(ctrl, library):
    with pytest.raises(ValueError):
        ctrl.reopen()
    info = {'kind': 'feed', 'title': 'Podcast', 'entries': []}
    ctrl._status = {'state': 'info', 'url': 'https://example/feed.rss', 'info': info}
    fake_download(ctrl)
    fake_convert(ctrl)
    with mock.patch.object(utils, 'tag_mp3'):
        ctrl.start_import('Mein Podcast', [{'url': 'https://y/1', 'title': 'Folge 1'}])
        wait(ctrl)
    assert ctrl._status['url'] == 'https://example/feed.rss'

    ctrl.reopen()
    assert ctrl._status == {'state': 'info', 'url': 'https://example/feed.rss', 'info': info,
                            'target_folder': 'Mein_Podcast'}


def test_convert_copies_mp3(ctrl, tmp_path):
    commands = []

    def convert_cmd(*args, **kwargs):
        commands.append(kwargs)
        return [sys.executable, '-c', 'pass']

    with mock.patch.object(utils, 'ffmpeg_convert_cmd', side_effect=convert_cmd):
        ctrl._convert({'audio': str(tmp_path / '0001.MP3'), 'duration': 10}, str(tmp_path / 'out.mp3'), None, None)
        ctrl._convert({'audio': str(tmp_path / '0002.webm'), 'duration': 10}, str(tmp_path / 'out.mp3'), None, None)
    assert [c['copy'] for c in commands] == [True, False]


def test_download_takes_the_embedded_cover(ctrl, tmp_path):
    src_dir = tmp_path / 'src'
    src_dir.mkdir()
    make_tagged_mp3(src_dir / '0001.mp3', cover=b'large picture')
    result = {'duration': 3606, 'requested_downloads': [{'filepath': str(src_dir / '0001.mp3')}]}
    ctrl._small_jpeg = lambda image, *args: b'small ' + open(image, 'rb').read()

    with mock.patch.object(ytimport, '_import_yt_dlp', return_value=fake_yt_dlp(result)):
        source = ctrl._download('https://cdn.example/1.mp3', str(src_dir), 1, cover=True)

    assert source['cover'] == b'small large picture'
    assert source['duration'] == 3606
    # Only the audio is left in the working directory
    assert os.listdir(src_dir) == ['0001.mp3']
