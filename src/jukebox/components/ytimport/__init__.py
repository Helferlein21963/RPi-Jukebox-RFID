"""
Import audio from YouTube (and other sites supported by yt-dlp), podcast feeds and direct links to audio
files into the music library.

Workflow (driven by the web app, page *Import*):

1. :meth:`YtImport.fetch_info` loads the metadata of a link: title, channel, playlist entries, chapters.
   A podcast feed (RSS) is listed like a playlist, with the date of each episode.
2. The user edits folder name, artist, album, titles and order, and can split a video into its chapters.
3. :meth:`YtImport.start_import` downloads every track with yt-dlp, converts it to MP3 with ffmpeg (or cuts
   the chapter out; MP3 sources are copied, not encoded again), writes the tags (title, artist, album, track
   number, thumbnail or the cover of the source as cover) and moves the finished folder into the music
   library. Then the MPD database is updated.

RPC calls and ``plugs.call`` are processed one after another, so everything that takes longer runs in a
worker thread and the RPC call returns immediately. The progress is published on the topic
``ytimport.status`` (see :meth:`YtImport.get_status`). The worker runs with a lower CPU priority, so that
playback keeps running smoothly on a small Raspberry Pi.

yt-dlp and mutagen are imported on first use: the plugin also loads when they are not installed, and the
web app can install / update them with :meth:`YtImport.update_ytdlp`.

Configuration (``jukebox.yaml``, all optional)::

    ytimport:
      audio_quality: 2
      js_runtime: node
      js_runtime_path: ''
      nice: 19
      max_playlist_entries: 200
      tmp_dir: ../../shared/tmp/ytimport
      ffmpeg: ffmpeg
"""

import glob
import importlib
import importlib.metadata
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from typing import Optional, Tuple

import components.player
import jukebox.cfghandler
import jukebox.playlistgenerator as playlistgenerator
import jukebox.plugs as plugs
import jukebox.publishing
import misc
from components.ytimport import utils

logger = logging.getLogger('jb.ytimport')
logger_ytdlp = logging.getLogger('jb.ytimport.ytdlp')
cfg = jukebox.cfghandler.get_handler('jukebox')

STATUS_TOPIC = 'ytimport.status'

#: Packages installed / updated by :meth:`YtImport.update_ytdlp`.
#: ``yt-dlp[default]`` brings ``yt-dlp-ejs`` in the version matching yt-dlp (needed for YouTube)
PIP_PACKAGES = ['yt-dlp[default]', 'mutagen']

#: Busy states: no other job can start meanwhile
BUSY_STATES = ('fetching', 'importing', 'updating')

THUMBNAIL_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')

#: A direct link to an audio file names no title: it is read from the ID3 tag at the start of the file,
#: which is loaded up to this size (a tag with a large cover has about 1 MB)
REMOTE_ID3_MAX_SIZE = 2 * 1024 * 1024
REMOTE_ID3_TIMEOUT = 15

#: At most this many folders are listed to choose from
MAX_FOLDERS = 2000


def _is_mp3(path: str) -> bool:
    return path.lower().endswith('.mp3')


class ImportCancelled(Exception):
    """The user cancelled the running job"""
    pass


def _import_yt_dlp():
    """Import yt-dlp on first use (it may be installed only while the jukebox is running)"""
    try:
        import yt_dlp
    except ImportError:
        importlib.invalidate_caches()
        try:
            import yt_dlp
        except ImportError as e:
            raise RuntimeError('yt-dlp is not installed. Install it on the Import page.') from e
    return yt_dlp


def _installed_version(package: str) -> Optional[str]:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


def _lower_priority(nice: int):
    """Lower the CPU priority of the calling thread (on Linux nice is per thread, child processes inherit it)"""
    if nice > 0 and hasattr(os, 'nice'):
        try:
            os.nice(nice)
        except OSError as e:
            logger.warning(f"Could not lower the priority: {e}")


class YtImport:
    """Control class of the YouTube import. RPC: ``ytimport.ctrl.<method>``"""

    def __init__(self):
        with cfg:
            self._quality = int(cfg.setndefault('ytimport', 'audio_quality', value=2))
            self._js_runtime = cfg.setndefault('ytimport', 'js_runtime', value='node')
            self._js_runtime_path = cfg.setndefault('ytimport', 'js_runtime_path', value='') or None
            self._nice = int(cfg.setndefault('ytimport', 'nice', value=19))
            self._max_entries = int(cfg.setndefault('ytimport', 'max_playlist_entries', value=200))
            self._tmp_base = os.path.abspath(cfg.setndefault('ytimport', 'tmp_dir', value='../../shared/tmp/ytimport'))
            self._ffmpeg = cfg.setndefault('ytimport', 'ffmpeg', value='ffmpeg')
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._cancel = threading.Event()
        self._proc: Optional[subprocess.Popen] = None
        self._status = {'state': 'idle'}
        self._last_publish = 0.0
        self._versions: Optional[dict] = None
        # Info of the last import ({url, info, folder}), to add more tracks of the same link (reopen)
        self._last_info: Optional[dict] = None
        # Left over from an import that was interrupted by a shutdown
        for job_dir in glob.glob(os.path.join(self._tmp_base, 'job_*')):
            shutil.rmtree(job_dir, ignore_errors=True)
        self._publish(force=True)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def _publish(self, force=False):
        """Publish the status. Progress updates are limited to about one per second"""
        now = time.monotonic()
        if not force and now - self._last_publish < 1.0:
            return
        self._last_publish = now
        # The publisher is thread-local: always get it in the thread that sends
        jukebox.publishing.get_publisher().send(STATUS_TOPIC, self._status)

    def _set_status(self, force=False, **kwargs):
        with self._lock:
            self._status = {**self._status, **kwargs}
        self._publish(force)

    def _new_status(self, state, **kwargs):
        """Replace the status (drops the values of the previous state) and publish it"""
        with self._lock:
            self._status = {'state': state, **kwargs}
        self._publish(force=True)

    def _is_busy(self):
        return self._thread is not None and self._thread.is_alive()

    def _start_job(self, state, job, *args, **status):
        """Set the new status and start ``job`` in a worker thread"""
        with self._lock:
            if self._is_busy():
                raise RuntimeError(f"Busy: '{self._status.get('state')}' is running")
            self._cancel.clear()
            self._new_status(state, **status)
            self._thread = threading.Thread(target=self._run_job, args=(job, *args), name='YtImport', daemon=True)
            self._thread.start()

    def _run_job(self, job, *args):
        _lower_priority(self._nice)
        try:
            job(*args)
        except Exception as e:
            # The folder of an import: it can be tried again with reopen
            keep = {key: self._status[key] for key in ('url', 'folder') if self._status.get(key)}
            if isinstance(e, ImportCancelled) or self._cancel.is_set():
                logger.info('Cancelled')
                self._new_status('cancelled', **keep)
            else:
                logger.error(f"{self._status.get('state')} failed: {e.__class__.__name__}: {e}")
                self._new_status('error', error=str(e), **keep)

    def _check_cancel(self):
        if self._cancel.is_set():
            raise ImportCancelled()

    @plugs.tag
    def get_status(self) -> dict:
        """
        Current status (also published on ``ytimport.status``)::

            {'state': 'idle' | 'fetching' | 'info' | 'importing' | 'done' | 'cancelled' | 'error' | 'updating'
                      | 'updated',
             'url': ..., 'info': {...} (state 'info', see utils.build_info), 'target_folder': ... (after reopen),
             'target': 'new' | 'existing',
             'folder': ..., 'current': 1, 'total': 12, 'track_title': ..., 'phase': 'download' | 'convert',
             'percent': 42.0, 'failed': [{'title': ..., 'error': ...}], 'error': ..., 'output': ...}
        """
        with self._lock:
            return dict(self._status)

    @plugs.tag
    def reset(self) -> None:
        """Back to 'idle' (forget the loaded info or the last result). Ignored while a job runs"""
        with self._lock:
            if not self._is_busy():
                self._new_status('idle')

    @plugs.tag
    def cancel(self) -> None:
        """Cancel the running job. A running conversion is stopped, the partial import is deleted"""
        self._cancel.set()
        proc = self._proc
        if proc is not None and proc.poll() is None:
            proc.terminate()

    # ------------------------------------------------------------------
    # Versions / installation
    # ------------------------------------------------------------------

    @plugs.tag
    def get_versions(self, refresh: bool = False) -> dict:
        """
        Installed tools::

            {'ytdlp': '2026.10.26' | None, 'ytdlp_loaded': version in use, 'restart_required': bool,
             'ejs': version | None, 'mutagen': version | None, 'ffmpeg': bool, 'js_runtime': 'node',
             'js_runtime_version': '20.19.1' | None (not found), 'js_runtime_supported': bool | None (unknown),
             'js_runtime_min': '22.0.0' | None}

        The first check loads yt-dlp and runs the JS runtime, which takes a moment on a small Raspberry Pi:
        the result is kept until the next installation (or ``refresh``)

        :param refresh: Check again
        """
        if self._versions is None or refresh:
            self._versions = self._check_versions()
        return dict(self._versions)

    def _check_versions(self) -> dict:
        # Loads yt-dlp (if installed), so do it first
        js_runtime = self._js_runtime_info()
        ytdlp_module = sys.modules.get('yt_dlp')
        loaded = getattr(getattr(ytdlp_module, 'version', None), '__version__', None) if ytdlp_module else None
        installed = _installed_version('yt-dlp')
        return {
            'ytdlp': installed,
            'ytdlp_loaded': loaded,
            'restart_required': bool(loaded and installed and loaded != installed),
            'ejs': _installed_version('yt-dlp-ejs'),
            'mutagen': _installed_version('mutagen'),
            'ffmpeg': shutil.which(self._ffmpeg) is not None,
            'js_runtime': self._js_runtime,
            **js_runtime,
        }

    def _js_runtime_info(self) -> dict:
        """Version of the JS runtime and whether yt-dlp accepts it (yt-dlp's own check, e.g. node >= 22)"""
        runtime_cls = None
        try:
            _import_yt_dlp()
            from yt_dlp.globals import supported_js_runtimes
            runtime_cls = supported_js_runtimes.value.get(self._js_runtime)
        except Exception as e:
            logger.debug(f"Could not check the JS runtime with yt-dlp: {e}")
        if runtime_cls is None:
            found = shutil.which(self._js_runtime_path or self._js_runtime) is not None
            return {'js_runtime_version': '?' if found else None, 'js_runtime_supported': None,
                    'js_runtime_min': None}
        info = runtime_cls(path=self._js_runtime_path).info
        min_version = getattr(runtime_cls, 'MIN_SUPPORTED_VERSION', None)
        return {
            'js_runtime_version': info.version if info else None,
            'js_runtime_supported': bool(info and info.supported),
            'js_runtime_min': '.'.join(str(v) for v in min_version) if min_version else None,
        }

    @plugs.tag
    def update_ytdlp(self) -> None:
        """
        Install or update yt-dlp (with yt-dlp-ejs) and mutagen in the jukebox' Python environment.

        Runs in the background; afterwards the state is 'updated'. An update of an already loaded yt-dlp is
        used after a restart of the jukebox service (``restart_required`` in :meth:`get_versions`).
        """
        self._start_job('updating', self._job_update)

    def _job_update(self):
        cmd = [sys.executable, '-m', 'pip', 'install', '--upgrade', '--no-cache-dir', *PIP_PACKAGES]
        logger.info(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, shell=False, check=False, capture_output=True, text=True, timeout=1800)
        output = (result.stdout + result.stderr).strip()
        tail = '\n'.join(output.splitlines()[-15:])
        if result.returncode != 0:
            logger.error(f"pip failed: {tail}")
            raise RuntimeError(f"pip install failed:\n{tail}")
        importlib.invalidate_caches()
        logger.info(f"yt-dlp {_installed_version('yt-dlp')} installed")
        self._new_status('updated', output=tail, versions=self.get_versions(refresh=True))

    # ------------------------------------------------------------------
    # yt-dlp
    # ------------------------------------------------------------------

    def _ydl_options(self, **options) -> dict:
        return {
            'quiet': True,
            'no_warnings': False,
            'noprogress': True,
            'logger': logger_ytdlp,
            'js_runtimes': {self._js_runtime: {'path': self._js_runtime_path} if self._js_runtime_path else {}},
            **options,
        }

    @plugs.tag
    def fetch_info(self, url: str) -> None:
        """
        Load the metadata of a link in the background. Result: state 'info' with ``info`` in the status

        :param url: Link to a video or a playlist (YouTube, YouTube Music, or any site yt-dlp supports), to a
            podcast feed (RSS) or directly to an audio file (e.g. an MP3 of a podcast episode)
        """
        url = str(url or '').strip()
        if not url.startswith(('http://', 'https://')):
            raise ValueError('Please enter a link starting with http:// or https://')
        self._start_job('fetching', self._job_fetch, url, url=url)

    def _job_fetch(self, url):
        yt_dlp = _import_yt_dlp()
        with yt_dlp.YoutubeDL(self._ydl_options()) as ydl:
            raw = ydl.extract_info(url, download=False, process=False)
            # Links like watch?v=...&list=... or short links point to another URL first
            for _ in range(5):
                if not raw or raw.get('_type') not in ('url', 'url_transparent'):
                    break
                self._check_cancel()
                raw = ydl.extract_info(raw['url'], download=False, process=False)
            if not raw:
                raise RuntimeError('No information found for this link')
            info = utils.build_info(raw, url, self._max_entries)
        self._check_cancel()
        if raw.get('direct') and info['kind'] == 'video':
            self._add_file_tags(info)
            self._check_cancel()
        if not info['entries']:
            raise RuntimeError('No playable entries found')
        logger.info(f"Info loaded: {info['kind']} '{info['title']}' with {len(info['entries'])} entries")
        self._new_status('info', url=url, info=info)

    def _add_file_tags(self, info):
        """
        A direct link to an audio file is only known by its file name (e.g. a UUID): take title, album and
        artist from the ID3 tag of the file instead. Album (else title) becomes the suggested folder name.
        """
        entry = info['entries'][0]
        try:
            tags = self._remote_id3(entry['url'])
        except Exception as e:
            logger.warning(f"Could not read the tags of '{entry['url']}': {e.__class__.__name__}: {e}")
            return
        if not tags['title']:
            return
        entry['title'] = tags['title']
        info['title'] = tags['album'] or tags['title']
        info['uploader'] = utils.clean_artist(tags['artist']) or tags['album']
        info['folder'] = utils.sanitize_folder(info['title'])

    @staticmethod
    def _remote_id3(url) -> dict:
        """Title, artist and album from the ID3 tag of a remote MP3 file; loads only the start of the file"""
        def read_start(size):
            request = urllib.request.Request(url, headers={'Range': f'bytes=0-{size - 1}',
                                                           'User-Agent': 'Mozilla/5.0 (Phoniebox)'})
            with urllib.request.urlopen(request, timeout=REMOTE_ID3_TIMEOUT) as response:
                # A server that ignores the range sends the whole file: read only what is needed
                return response.read(size)

        size = utils.id3_tag_size(read_start(utils.ID3_HEADER_SIZE))
        if size is None or size > REMOTE_ID3_MAX_SIZE:
            return {'title': '', 'artist': '', 'album': ''}
        return utils.id3_summary(read_start(size))

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    @staticmethod
    def _library_path() -> str:
        return os.path.abspath(os.path.expanduser(components.player.get_music_library_path()))

    def _target_folder(self, name):
        """Name and path of a new folder (directly in the music library)"""
        folder = utils.sanitize_folder(name)
        if not folder:
            raise ValueError('Please enter a folder name')
        library = self._library_path()
        target = os.path.abspath(os.path.join(library, folder))
        if os.path.commonpath([library, target]) != library or target == library:
            raise ValueError(f"Invalid folder name: '{name}'")
        return folder, target

    def _existing_folder(self, name) -> Optional[Tuple[str, str]]:
        """
        ``(folder, path)`` of an existing folder of the music library, None if there is none of that name.

        ``name`` is a path relative to the library as listed by :meth:`list_folders`, or a name that becomes
        the name of an existing folder when it is cleaned (``Max übernachtet`` → ``Max_uebernachtet``).
        """
        name = str(name or '').strip().strip('/')
        library = self._library_path()
        for candidate in dict.fromkeys([name, utils.sanitize_folder(name)]):
            if not candidate:
                continue
            path = os.path.abspath(os.path.join(library, candidate))
            if os.path.commonpath([library, path]) == library and path != library and os.path.isdir(path):
                return os.path.relpath(path, library).replace(os.sep, '/'), path
        return None

    def _folder_files(self, folder) -> list:
        """Playable files of a folder in the order the player plays them (as the playlist generator sorts)"""
        collector = playlistgenerator.PlaylistCollector(self._library_path())
        collector.get_directory_content(folder)
        return [entry['name'] for entry in collector.playlist if entry['type'] == 'file']

    @plugs.tag
    def list_folders(self) -> list:
        """
        Folders of the music library (to add tracks to), sorted like the library::

            [{'folder': 'Max_uebernachtet', 'tracks': 12}, ...]
        """
        library = self._library_path()
        result = []
        for root, dirs, files in os.walk(library, followlinks=True):
            dirs[:] = sorted((d for d in dirs if not d.startswith('.')), key=str.casefold)
            if root == library:
                continue
            tracks = sum(1 for entry in os.scandir(root) if playlistgenerator.PlaylistCollector._is_valid(entry))
            result.append({'folder': os.path.relpath(root, library).replace(os.sep, '/'), 'tracks': tracks})
            if len(result) >= MAX_FOLDERS:
                break
        return sorted(result, key=lambda entry: entry['folder'].casefold())

    @plugs.tag
    def folder_info(self, name: str) -> dict:
        """
        What happens with the folder name the user entered.

        A new folder (created directly in the music library)::

            {'folder': 'Max_uebernachtet_bei_Oma', 'exists': False}

        An existing folder (the tracks are added to it)::

            {'folder': 'Max_uebernachtet', 'exists': True, 'numbered': True, 'artist': ..., 'album': ...,
             'tracks': [{'file': '01 - Kapitel 1.mp3', 'title': 'Kapitel 1'}, ...]}

        ``tracks`` are in the order they are played; ``numbered``: all files start with a number, new tracks
        get the next numbers (else they sort in alphabetically). Artist and album are those of the first MP3.
        """
        existing = self._existing_folder(name)
        if existing is None:
            return {'folder': utils.sanitize_folder(name), 'exists': False}
        folder, path = existing
        files = self._folder_files(folder)
        # Of the first MP3 with tags (a few files only: a folder without tags is not read completely)
        mp3s = [f for f in files if f.lower().endswith('.mp3')][:5]
        tags = next((t for t in (utils.file_tags(os.path.join(path, f)) for f in mp3s) if t['artist'] or t['album']),
                    {'artist': '', 'album': ''})
        return {
            'folder': folder,
            'exists': True,
            'numbered': all(utils.track_number(f) is not None for f in files),
            'artist': tags['artist'],
            'album': tags['album'],
            'tracks': [{'file': f, 'title': utils.strip_number(os.path.splitext(f)[0])} for f in files],
        }

    @plugs.tag
    def start_import(self, folder: str, tracks: list, artist: str = '', album: str = '', cover: bool = True,
                     target: str = 'new', reorder: bool = False) -> str:
        """
        Start the import in the background. Result: state 'done' (or 'error' / 'cancelled')

        :param folder: Name of the new folder in the music library (is cleaned, see utils.sanitize_folder), or
            of an existing folder (``target='existing'``)
        :param tracks: ``[{url, title, start?, end?}]`` in the order of the folder; ``start``/``end`` in
            seconds cut a part (chapter) out of the video. With ``reorder`` the whole folder in the new order:
            ``{file}`` stands for a file that is in the folder already
        :param artist: Artist (and album artist) of all tracks
        :param album: Album of all tracks
        :param cover: Embed the thumbnail as cover
        :param target: ``new``: create the folder, it must not exist yet. ``existing``: add the tracks to an
            existing folder, named to fit it (see utils.plan_append_names)
        :param reorder: Only with ``existing``: rename all files of the folder to ``01 - ...`` in the order of
            ``tracks``. Files of the folder missing in ``tracks`` keep their order at the end
        :return: The folder name
        """
        reorder = bool(reorder) and target == 'existing'
        if target == 'existing':
            existing = self._existing_folder(folder)
            if existing is None:
                raise FileNotFoundError(f"Folder '{folder}' does not exist")
            folder_name, path = existing
        elif target == 'new':
            folder_name, path = self._target_folder(folder)
            if os.path.exists(path):
                raise FileExistsError(f"Folder '{folder_name}' exists already")
        else:
            raise ValueError(f"Invalid target: '{target}'")

        tracks = utils.normalize_tracks(tracks, allow_existing=reorder)
        if reorder:
            tracks = self._complete_order(folder_name, tracks)
        new_count = sum(1 for track in tracks if 'url' in track)
        if not new_count:
            raise ValueError('No tracks selected')
        options = {
            'artist': str(artist or '').strip(),
            'album': str(album or '').strip(),
            'cover': bool(cover),
            'target': target,
            'reorder': reorder,
        }
        with self._lock:
            if self._status.get('state') == 'info':
                self._last_info = {'url': self._status.get('url'), 'info': self._status.get('info')}
            if self._last_info is not None:
                self._last_info['folder'] = folder_name
            url = (self._last_info or {}).get('url')
        self._start_job('importing', self._job_import, folder_name, path, tracks, options,
                        folder=folder_name, url=url, target=target, current=0, total=new_count, track_title='',
                        phase='download', percent=0, failed=[])
        return folder_name

    def _complete_order(self, folder, tracks):
        """The whole folder in the new order: checks the named files, adds the missing ones at the end"""
        files = self._folder_files(folder)
        named = [track['file'] for track in tracks if 'file' in track]
        unknown = sorted(set(named) - set(files))
        if unknown:
            raise ValueError(f"Not in folder '{folder}': {', '.join(unknown)}")
        if len(named) != len(set(named)):
            raise ValueError('A file is listed twice')
        return tracks + [{'file': f} for f in files if f not in named]

    @plugs.tag
    def reopen(self) -> None:
        """
        Back to the info of the last import (state 'info'), e.g. to add more episodes of a podcast to the same
        folder without loading the link again. ``target_folder`` in the status is the folder used last
        """
        with self._lock:
            if self._is_busy():
                raise RuntimeError(f"Busy: '{self._status.get('state')}' is running")
            if not self._last_info or not self._last_info.get('info'):
                raise ValueError('Nothing to continue: load a link first')
            self._new_status('info', url=self._last_info['url'], info=self._last_info['info'],
                             target_folder=self._last_info.get('folder'))

    def _job_import(self, folder_name, path, tracks, options):
        os.makedirs(self._tmp_base, exist_ok=True)
        job_dir = tempfile.mkdtemp(prefix='job_', dir=self._tmp_base)
        try:
            self._import_tracks(job_dir, folder_name, path, tracks, options)
        finally:
            shutil.rmtree(job_dir, ignore_errors=True)

    def _import_tracks(self, job_dir, folder_name, path, tracks, options):
        src_dir = os.path.join(job_dir, 'src')
        out_dir = os.path.join(job_dir, 'out')
        os.makedirs(src_dir)
        os.makedirs(out_dir)
        new_tracks = [track for track in tracks if 'url' in track]
        total = len(new_tracks)
        # Index of the last track that needs a download: delete it afterwards to save space
        last_use = {track['url']: idx for idx, track in enumerate(new_tracks)}
        sources = {}
        failed = []
        logger.info(f"Import of {total} tracks into '{folder_name}' ({options['target']}"
                    f"{', new order' if options['reorder'] else ''})")

        for idx, track in enumerate(new_tracks):
            self._check_cancel()
            number = idx + 1
            self._set_status(force=True, current=number, track_title=track['title'], phase='download', percent=0)
            try:
                if track['url'] not in sources:
                    sources[track['url']] = self._download(track['url'], src_dir, number, options['cover'])
                source = sources[track['url']]
                self._import_track(source, os.path.join(out_dir, f'{number:04d}.mp3'), track)
                track['converted'] = os.path.join(out_dir, f'{number:04d}.mp3')
                track['cover'] = source.get('cover')
            except ImportCancelled:
                raise
            except Exception as e:
                if self._cancel.is_set():
                    raise ImportCancelled() from e
                logger.error(f"Track {number} '{track['title']}' failed: {e.__class__.__name__}: {e}")
                failed.append({'title': track['title'], 'error': str(e)})
                self._set_status(force=True, failed=failed)
            if last_use[track['url']] == idx and track['url'] in sources:
                self._remove_source(sources.pop(track['url']))

        if len(failed) == total:
            raise RuntimeError(f"No track could be imported: {failed[0]['error']}")
        self._check_cancel()
        # Failed tracks leave no gap in the numbering
        items = [track for track in tracks if 'file' in track or 'converted' in track]
        new_files, renames = self._name_tracks(folder_name, items, out_dir, options)
        if options['target'] == 'new':
            self._finish(folder_name, out_dir, path)
        else:
            self._finish_existing(folder_name, out_dir, path, new_files, renames)
        logger.info(f"Import into '{folder_name}' done ({total - len(failed)} of {total} tracks)")
        self._new_status('done', folder=folder_name, url=self._status.get('url'), target=options['target'],
                         total=total, imported=total - len(failed), failed=failed)

    def _name_tracks(self, folder_name, items, out_dir, options):
        """
        Give the converted tracks their file names and tags

        :return: ``(new_files, renames)``: names of the new files, ``[(old, new, number, total)]`` for the files
            of the folder
        """
        new_items = [item for item in items if 'converted' in item]
        if options['reorder']:
            names = utils.plan_reorder_names(items)
            positions = {id(item): idx for idx, item in enumerate(items)}
            numbers = [(positions[id(item)] + 1, len(items)) for item in new_items]
            new_names = [names[positions[id(item)]] for item in new_items]
            renames = [(item['file'], name, idx + 1, len(items))
                       for idx, (item, name) in enumerate(zip(items, names)) if 'file' in item]
        elif options['target'] == 'existing':
            new_names, numbered = utils.plan_append_names(self._folder_files(folder_name),
                                                          [item['title'] for item in new_items])
            numbers = [(utils.track_number(name), None) if numbered else (None, None) for name in new_names]
            renames = []
        else:
            width = max(2, len(str(len(new_items))))
            new_names = [utils.track_filename(idx + 1, item['title'], width) for idx, item in enumerate(new_items)]
            numbers = [(idx + 1, len(new_items)) for idx in range(len(new_items))]
            renames = []

        for item, name, (number, total) in zip(new_items, new_names, numbers):
            destination = os.path.join(out_dir, name)
            os.rename(item['converted'], destination)
            utils.tag_mp3(destination, item['title'], options['artist'], options['album'], number, total,
                          item.get('cover'))
        return new_names, renames

    def _import_track(self, source, destination, track):
        """Convert (or cut out) one track"""
        self._check_cancel()
        self._set_status(force=True, phase='convert', percent=0)
        self._convert(source, destination, track['start'], track['end'])

    def _finish(self, folder_name, out_dir, target):
        """Move the finished folder into the library, set the permissions, update the MPD database"""
        if os.path.exists(target):
            raise FileExistsError(f"Folder '{folder_name}' exists already")
        shutil.move(out_dir, target)
        self._set_permissions(target)
        # Not update_wait: that would block all other plugin calls (e.g. cards) while MPD scans
        plugs.call_ignore_errors('player', 'ctrl', 'update')

    def _finish_existing(self, folder_name, out_dir, target, new_files, renames):
        """
        Add the new files to an existing folder and rename its files to the new order. Renaming goes over
        temporary names, so that no file overwrites another when names are swapped. The player follows the
        renamed files, also while it plays the folder
        """
        if not os.path.isdir(target):
            raise FileNotFoundError(f"Folder '{folder_name}' does not exist any more")
        changed = [(old, new) for old, new, _, _ in renames if old != new]
        for name in new_files:
            if os.path.exists(os.path.join(target, name)) and name not in {old for old, _ in changed}:
                raise FileExistsError(f"'{name}' exists already in '{folder_name}'")
        temporary = []
        for idx, (old, new) in enumerate(changed):
            temp = f'.ytimport_{idx}{os.path.splitext(old)[1]}'
            os.rename(os.path.join(target, old), os.path.join(target, temp))
            temporary.append((temp, new))
        for temp, new in temporary:
            os.rename(os.path.join(target, temp), os.path.join(target, new))
        for name in new_files:
            shutil.move(os.path.join(out_dir, name), os.path.join(target, name))
        self._renumber(target, renames)
        if changed:
            logger.info(f"Renamed {len(changed)} files of '{folder_name}' to the new order")
        self._set_permissions(target)
        if changed:
            self._player_follow(target, [(os.path.join(target, old), os.path.join(target, new))
                                         for old, new in changed])
        else:
            plugs.call_ignore_errors('player', 'ctrl', 'update')

    @staticmethod
    def _player_follow(target, renames):
        """
        Let the player follow the renamed files (queue, remembered positions, cards) and update its database.
        Without that (player without ``files_renamed``) at least the database is updated
        """
        try:
            plugs.call('player', 'ctrl', 'files_renamed', args=[target, renames])
        except Exception as e:
            logger.warning(f"Player could not follow the renamed files: {e.__class__.__name__}: {e}")
            plugs.call_ignore_errors('player', 'ctrl', 'update')

    @staticmethod
    def _renumber(target, renames):
        """The track numbers of the files of the folder follow the new order (the library sorts albums by them)"""
        for _, name, number, total in renames:
            if not name.lower().endswith('.mp3'):
                continue
            try:
                utils.set_track_number(os.path.join(target, name), number, total)
            except Exception as e:
                logger.warning(f"Could not set the track number of '{name}': {e}")

    @staticmethod
    def _set_permissions(target):
        with cfg:
            check_user_rights = cfg.getn('playermpd', 'library', 'check_user_rights', default=True)
        if check_user_rights is True:
            try:
                misc.recursive_chmod(target, mode_files=0o666, mode_dirs=0o777)
            except OSError as e:
                logger.warning(f"Could not set permissions of '{target}': {e}")

    def _progress_hook(self, data):
        if self._cancel.is_set():
            raise ImportCancelled()
        if data.get('status') == 'downloading':
            size = data.get('total_bytes') or data.get('total_bytes_estimate')
            if size:
                self._set_status(percent=round(min(100.0, 100.0 * (data.get('downloaded_bytes') or 0) / size), 1))

    def _download(self, url, src_dir, number, cover) -> dict:
        """Download the audio of ``url`` (and the thumbnail). Returns ``{audio, cover, duration}``"""
        yt_dlp = _import_yt_dlp()
        name = f'{number:04d}'
        options = self._ydl_options(
            format='bestaudio/best',
            outtmpl=os.path.join(src_dir, f'{name}.%(ext)s'),
            noplaylist=True,
            writethumbnail=cover,
            overwrites=True,
            progress_hooks=[self._progress_hook],
        )
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
        if info.get('_type') == 'playlist':
            info = next(e for e in info.get('entries') or [] if e)
        downloads = info.get('requested_downloads') or []
        audio = downloads[0].get('filepath') if downloads else None
        if not audio or not os.path.exists(audio):
            raise RuntimeError('Download failed (no file)')
        source = {'audio': audio, 'cover': None, 'duration': info.get('duration')}
        if cover:
            source['cover'] = self._read_cover(src_dir, name)
            if source['cover'] is None and _is_mp3(audio):
                source['cover'] = self._read_embedded_cover(audio, src_dir, name)
        return source

    def _read_cover(self, src_dir, name) -> Optional[bytes]:
        """Convert the downloaded thumbnail to a small JPEG and return its bytes (None if not available)"""
        thumbnails = [f for f in glob.glob(os.path.join(src_dir, f'{name}.*'))
                      if f.lower().endswith(THUMBNAIL_EXTENSIONS)]
        if not thumbnails:
            return None
        try:
            return self._small_jpeg(thumbnails[0], src_dir, name)
        finally:
            for thumbnail in thumbnails:
                os.remove(thumbnail)

    def _read_embedded_cover(self, audio, src_dir, name) -> Optional[bytes]:
        """The cover embedded in the downloaded MP3 (e.g. of a podcast episode) as a small JPEG"""
        picture = utils.embedded_cover(audio)
        if not picture:
            return None
        image = os.path.join(src_dir, f'{name}_embedded.img')
        with open(image, 'wb') as f:
            f.write(picture)
        try:
            return self._small_jpeg(image, src_dir, name)
        finally:
            os.remove(image)

    def _small_jpeg(self, image, src_dir, name) -> Optional[bytes]:
        """Convert an image (often WebP or a large JPEG) to a JPEG of at most 500 pixels"""
        jpeg = os.path.join(src_dir, f'{name}_cover.jpg')
        result = subprocess.run(utils.ffmpeg_cover_cmd(self._ffmpeg, image, jpeg), shell=False,
                                check=False, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if result.returncode != 0 or not os.path.exists(jpeg):
            logger.warning(f"Could not convert the cover: {result.stderr.strip()}")
            return None
        with open(jpeg, 'rb') as f:
            data = f.read()
        os.remove(jpeg)
        return data

    @staticmethod
    def _remove_source(source):
        try:
            os.remove(source['audio'])
        except OSError:
            pass

    def _convert(self, source, destination, start, end):
        """Convert to MP3 with ffmpeg (an MP3 source is copied), publishes the progress, can be cancelled"""
        cmd = utils.ffmpeg_convert_cmd(self._ffmpeg, source['audio'], destination, self._quality, start, end,
                                       copy=_is_mp3(source['audio']))
        duration = (end - (start or 0)) if end is not None else (source.get('duration') or 0) - (start or 0)
        lines = []
        with subprocess.Popen(cmd, shell=False, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True) as proc:
            self._proc = proc
            try:
                for line in proc.stdout:
                    if self._cancel.is_set():
                        proc.terminate()
                        break
                    seconds = utils.parse_ffmpeg_progress(line)
                    if seconds is None:
                        if '=' not in line:
                            lines.append(line.strip())
                    elif duration > 0:
                        self._set_status(percent=round(min(100.0, 100.0 * seconds / duration), 1))
                proc.wait()
            finally:
                self._proc = None
        self._check_cancel()
        if proc.returncode != 0:
            message = ' '.join(line for line in lines if line)[-300:]
            raise RuntimeError(f"ffmpeg failed ({proc.returncode}): {message}")

    def exit(self):
        """
        Cancel a running job.

        The worker thread is not returned to the daemon to wait for: a hanging download or pip would block
        the shutdown. It is a daemon thread; what it leaves in ``tmp_dir`` is removed at the next start.
        """
        self.cancel()


# ---------------------------------------------------------------------------
# Plugin Initializer / Finalizer
# ---------------------------------------------------------------------------

ytimport_ctrl: Optional[YtImport] = None


@plugs.initialize
def initialize():
    global ytimport_ctrl
    ytimport_ctrl = YtImport()
    plugs.register(ytimport_ctrl, name='ctrl')


@plugs.atexit
def atexit(**ignored_kwargs):
    if ytimport_ctrl is not None:
        ytimport_ctrl.exit()
