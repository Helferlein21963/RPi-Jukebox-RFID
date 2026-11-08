"""
Helpers of the YouTube import that do not depend on a running jukebox: name cleaning, preparing the metadata
for the web app, building the ffmpeg command line and writing the MP3 tags.
"""

import datetime
import io
import itertools
import re
from typing import List, Optional

from slugify import slugify

#: Umlauts are written out (e.g. ``Max_uebernachtet_bei_Oma``)
#: instead of being reduced to the bare vowel
UMLAUT_REPLACEMENTS = [
    ['Ä', 'Ae'], ['Ö', 'Oe'], ['Ü', 'Ue'],
    ['ä', 'ae'], ['ö', 'oe'], ['ü', 'ue'],
    ['ß', 'ss'],
]

#: Titles YouTube shows for playlist entries that can't be downloaded
UNAVAILABLE_TITLES = ('[private video]', '[deleted video]', '[unavailable video]')

FOLDER_MAX_LENGTH = 80
FILENAME_MAX_LENGTH = 100


def sanitize_folder(name: str) -> str:
    """
    Turn a title into a folder name for the music library.

    Only ASCII letters and digits remain, everything in between (spaces, ``-``, ``.``, ...) becomes a single
    ``_``, umlauts are written out. The result can't leave the music library (no ``/``, no ``..``).

    :param name: e.g. ``Max übernachtet bei Oma``
    :return: e.g. ``Max_uebernachtet_bei_Oma``, empty if nothing usable is left
    """
    folder = slugify(str(name or ''), separator='_', lowercase=False, replacements=UMLAUT_REPLACEMENTS,
                     regex_pattern=r'[^a-zA-Z0-9]+', max_length=FOLDER_MAX_LENGTH, word_boundary=True)
    return folder.strip('_')


def safe_filename(title: str) -> str:
    """
    Make a track title usable as a file name. Umlauts and spaces stay, characters that are not allowed in
    file names (on Linux and on Windows, e.g. for copies over Samba/FTP) are replaced.
    """
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', ' ', str(title or ''))
    name = re.sub(r'\s+', ' ', name).strip(' .')
    name = name[:FILENAME_MAX_LENGTH].rstrip(' .')
    return name or 'Track'


def track_filename(number: int, title: str, width: int = 2) -> str:
    """
    File name of a track: ``01 - Title.mp3``.

    The number leads with zeros so that the alphabetical order (as used by the playlist generator) is the
    track order.
    """
    return f'{number:0{width}d} - {safe_filename(title)}.mp3'


def clean_artist(name: Optional[str]) -> str:
    """Channel name as artist; drops the ``- Topic`` suffix of YouTube Music's auto-generated channels"""
    name = str(name or '').strip()
    return re.sub(r'\s+-\s+Topic$', '', name)


def _entry_url(entry: dict) -> Optional[str]:
    """Link of a playlist entry (flat extraction gives the URL, the ID or both)"""
    for key in ('webpage_url', 'url'):
        url = entry.get(key)
        if isinstance(url, str) and url.startswith(('http://', 'https://')):
            return url
    video_id = entry.get('id')
    if video_id and entry.get('ie_key', 'Youtube') == 'Youtube':
        return f'https://www.youtube.com/watch?v={video_id}'
    return None


def _thumbnail(raw: dict, entries: Optional[list] = None) -> Optional[str]:
    """
    URL of the best thumbnail (the last one in the list is the largest). A playlist without an own
    thumbnail (e.g. a podcast feed) gets the one of its first entry.
    """
    if raw.get('thumbnail'):
        return raw['thumbnail']
    thumbnails = [t for t in (raw.get('thumbnails') or []) if t.get('url')]
    if thumbnails:
        return thumbnails[-1]['url']
    return next((entry['thumbnail'] for entry in entries or [] if entry and entry.get('thumbnail')), None)


def _date(timestamp) -> Optional[str]:
    """Publication date ``YYYY-MM-DD`` (e.g. of a podcast episode) from a UNIX timestamp"""
    try:
        return datetime.datetime.fromtimestamp(int(timestamp), tz=datetime.timezone.utc).date().isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def build_chapters(raw: dict) -> List[dict]:
    """
    Chapters of a video as ``[{title, start, end}]`` (seconds). Missing end times are taken from the next
    chapter or the video duration, empty chapters are left out.
    """
    chapters = raw.get('chapters') or []
    duration = raw.get('duration')
    result = []
    for idx, chapter in enumerate(chapters):
        start = chapter.get('start_time')
        if start is None:
            continue
        end = chapter.get('end_time')
        if end is None:
            end = chapters[idx + 1].get('start_time') if idx + 1 < len(chapters) else duration
        if end is None or end <= start:
            continue
        title = str(chapter.get('title') or '').strip() or f'Kapitel {idx + 1}'
        result.append({'title': title, 'start': float(start), 'end': float(end)})
    return result


def build_info(raw: dict, url: str, max_entries: int) -> dict:
    """
    Prepare the metadata of yt-dlp (``extract_info(..., process=False)``) for the web app.

    :param raw: Result of yt-dlp for a video, a playlist, a podcast feed or a direct link to an audio file
    :param url: The link the user entered
    :param max_entries: At most this many playlist entries are listed
    :return: ``{kind, url, title, uploader, thumbnail, folder, truncated, entries}`` where each entry is
        ``{url, title, duration, date, available, chapters}``. ``kind`` is ``video``, ``playlist`` or
        ``feed`` (a list found by yt-dlp's generic extractor, i.e. a podcast feed)
    """
    title = str(raw.get('title') or '').strip()
    uploader = clean_artist(raw.get('uploader') or raw.get('channel') or raw.get('artist'))
    truncated = False
    raw_entries = []

    if raw.get('_type') in ('playlist', 'multi_video'):
        kind = 'feed' if raw.get('extractor') == 'generic' else 'playlist'
        # A feed names no artist: the title of the podcast is the best guess
        if kind == 'feed' and not uploader:
            uploader = title
        entries = []
        raw_entries = list(itertools.islice(raw.get('entries') or [], max_entries + 1))
        for entry in raw_entries:
            if not entry:
                continue
            if len(entries) >= max_entries:
                truncated = True
                break
            entry_url = _entry_url(entry)
            if entry_url is None:
                continue
            entry_title = str(entry.get('title') or entry.get('id') or '').strip()
            entries.append({
                'url': entry_url,
                'title': entry_title,
                'duration': entry.get('duration'),
                'date': _date(entry.get('timestamp')),
                'available': entry_title.lower() not in UNAVAILABLE_TITLES,
                'chapters': [],
            })
    else:
        kind = 'video'
        entries = [{
            'url': raw.get('webpage_url') or url,
            'title': title,
            'duration': raw.get('duration'),
            'date': _date(raw.get('timestamp')),
            'available': True,
            'chapters': build_chapters(raw),
        }]

    return {
        'kind': kind,
        'url': url,
        'title': title,
        'uploader': uploader,
        'thumbnail': _thumbnail(raw, raw_entries),
        'folder': sanitize_folder(title),
        'truncated': truncated,
        'entries': entries,
    }


def _optional_seconds(value) -> Optional[float]:
    if value is None or value == '':
        return None
    seconds = float(value)
    if seconds < 0:
        raise ValueError(f'Invalid time: {value}')
    return seconds


def normalize_tracks(tracks) -> List[dict]:
    """
    Check the track list sent by the web app.

    :param tracks: ``[{url, title, start?, end?}]`` in the order of the new folder. ``start``/``end``
        (seconds) cut a part (e.g. a chapter) out of the video
    :return: Cleaned list ``[{url, title, start, end}]``
    :raises ValueError: On a broken entry
    """
    if not isinstance(tracks, (list, tuple)):
        raise ValueError('tracks must be a list')
    result = []
    for track in tracks:
        if not isinstance(track, dict):
            raise ValueError(f'Invalid track: {track!r}')
        url = str(track.get('url') or '').strip()
        if not url.startswith(('http://', 'https://')):
            raise ValueError(f'Invalid link: {url!r}')
        title = re.sub(r'\s+', ' ', str(track.get('title') or '')).strip() or 'Track'
        start = _optional_seconds(track.get('start'))
        end = _optional_seconds(track.get('end'))
        if start is not None and end is not None and end <= start:
            raise ValueError(f"Track '{title}' ends before it starts")
        result.append({'url': url, 'title': title, 'start': start, 'end': end})
    return result


def ffmpeg_convert_cmd(ffmpeg: str, source: str, destination: str, quality: int,
                       start: Optional[float] = None, end: Optional[float] = None, copy: bool = False) -> List[str]:
    """
    ffmpeg command line: convert ``source`` (or the part from ``start`` to ``end``) to MP3 (VBR).

    Tags and an embedded cover of the source are dropped (they are written afterwards with :func:`tag_mp3`).
    Progress is written to stdout as ``key=value`` lines (``-progress pipe:1``).

    :param copy: The source is MP3 already (e.g. a podcast episode): copy the audio instead of encoding it
        again, which is much faster and keeps the quality
    """
    cmd = [ffmpeg, '-hide_banner', '-nostdin', '-loglevel', 'error', '-y']
    if start:
        cmd += ['-ss', f'{start:.3f}']
    cmd += ['-i', source]
    if end is not None:
        cmd += ['-t', f'{end - (start or 0):.3f}']
    cmd += ['-vn', '-map_metadata', '-1']
    if copy:
        cmd += ['-codec:a', 'copy']
    else:
        cmd += ['-codec:a', 'libmp3lame', '-q:a', str(int(quality))]
    cmd += ['-progress', 'pipe:1', '-nostats', destination]
    return cmd


def ffmpeg_cover_cmd(ffmpeg: str, source: str, destination: str, max_width: int = 500) -> List[str]:
    """ffmpeg command line: convert a thumbnail (often WebP) to a JPEG of at most ``max_width`` pixels"""
    return [ffmpeg, '-hide_banner', '-nostdin', '-loglevel', 'error', '-y', '-i', source,
            '-vf', f"scale='min({max_width},iw)':-2", '-frames:v', '1', destination]


def parse_ffmpeg_progress(line: str) -> Optional[float]:
    """Seconds already converted from a line of ``ffmpeg -progress`` (``out_time_us`` / ``out_time_ms``)"""
    key, _, value = line.strip().partition('=')
    # out_time_ms is in microseconds as well (an old ffmpeg naming mistake)
    if key in ('out_time_us', 'out_time_ms'):
        try:
            return max(0.0, int(value) / 1_000_000)
        except ValueError:
            return None
    return None


def tag_mp3(path: str, title: str, artist: str = '', album: str = '', track: Optional[int] = None,
            total: Optional[int] = None, cover: Optional[bytes] = None) -> None:
    """
    Write ID3 tags (v2.3, read by MPD and also by older car radios / players).

    ``artist`` is also the album artist: the web app groups albums (and the cover cache) by album artist
    and album.
    """
    from mutagen.id3 import ID3, APIC, TALB, TIT2, TPE1, TPE2, TRCK

    tags = ID3()
    tags.add(TIT2(encoding=3, text=title))
    if artist:
        tags.add(TPE1(encoding=3, text=artist))
        tags.add(TPE2(encoding=3, text=artist))
    if album:
        tags.add(TALB(encoding=3, text=album))
    if track is not None:
        tags.add(TRCK(encoding=3, text=f'{track}/{total}' if total else str(track)))
    if cover:
        tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=cover))
    tags.save(path, v2_version=3)


#: Size of the ID3v2 header at the start of a file
ID3_HEADER_SIZE = 10


def id3_tag_size(header: bytes) -> Optional[int]:
    """
    Total size (header included) of the ID3v2 tag a file starts with, from its first 10 bytes.

    :return: None if the data does not start with an ID3v2 tag
    """
    if len(header) < ID3_HEADER_SIZE or header[:3] != b'ID3':
        return None
    size_bytes = header[6:10]
    if any(b & 0x80 for b in size_bytes):
        return None
    # Syncsafe integer: 7 bits per byte
    size = (size_bytes[0] << 21) | (size_bytes[1] << 14) | (size_bytes[2] << 7) | size_bytes[3]
    footer = ID3_HEADER_SIZE if header[5] & 0x10 else 0
    return ID3_HEADER_SIZE + size + footer


def id3_summary(data: bytes) -> dict:
    """
    Title, artist and album from the ID3 tag at the start of an MP3 file (e.g. of a podcast episode).

    :param data: The start of the file, at least the whole tag (see :func:`id3_tag_size`)
    :return: ``{'title', 'artist', 'album'}``, empty strings for what is missing or if there is no usable tag
    """
    from mutagen.id3 import ID3, ID3NoHeaderError
    from mutagen import MutagenError

    result = {'title': '', 'artist': '', 'album': ''}
    try:
        tags = ID3(io.BytesIO(data))
    except (ID3NoHeaderError, MutagenError, OSError, ValueError, EOFError):
        return result
    for key, frame in (('title', 'TIT2'), ('artist', 'TPE1'), ('album', 'TALB')):
        if frame in tags:
            result[key] = re.sub(r'\s+', ' ', str(tags[frame])).strip()
    return result


def embedded_cover(path: str) -> Optional[bytes]:
    """The cover picture embedded in an MP3 file (front cover preferred), None if there is none"""
    from mutagen.id3 import ID3, ID3NoHeaderError
    from mutagen import MutagenError

    try:
        pictures = ID3(path).getall('APIC')
    except (ID3NoHeaderError, MutagenError, OSError):
        return None
    pictures = [p for p in pictures if p.data]
    if not pictures:
        return None
    front = [p for p in pictures if p.type == 3]
    return (front or pictures)[0].data
