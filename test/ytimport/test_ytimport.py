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


def test_check_folder(ctrl, library):
    (library / 'Max').mkdir()
    assert ctrl.check_folder('Max') == {'folder': 'Max', 'exists': True}
    assert ctrl.check_folder('Neuer Ordner') == {'folder': 'Neuer_Ordner', 'exists': False}
    assert ctrl.check_folder('???') == {'folder': '', 'exists': False}


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
    assert converts == [('01 - Kapitel 1.mp3', 0.0, 50.0), ('02 - Lied.mp3', None, None),
                        ('03 - Kapitel 2.mp3', 50.0, 100.0)]
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
