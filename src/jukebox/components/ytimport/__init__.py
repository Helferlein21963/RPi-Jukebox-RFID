"""
Import audio from YouTube (and other sites supported by yt-dlp) into the music library.

Workflow (driven by the web app, page *Import*):

1. :meth:`YtImport.fetch_info` loads the metadata of a link: title, channel, playlist entries, chapters.
2. The user edits folder name, artist, album, titles and order, and can split a video into its chapters.
3. :meth:`YtImport.start_import` downloads every track with yt-dlp, converts it to MP3 with ffmpeg (or cuts
   the chapter out), writes the tags (title, artist, album, track number, thumbnail as cover) and moves the
   finished folder into the music library. Then the MPD database is updated.

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
from typing import Optional

import components.player
import jukebox.cfghandler
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

    def _start_job(self, state, target, *args, **status):
        """Set the new status and start ``target`` in a worker thread"""
        with self._lock:
            if self._is_busy():
                raise RuntimeError(f"Busy: '{self._status.get('state')}' is running")
            self._cancel.clear()
            self._new_status(state, **status)
            self._thread = threading.Thread(target=self._run_job, args=(target, *args), name='YtImport', daemon=True)
            self._thread.start()

    def _run_job(self, target, *args):
        _lower_priority(self._nice)
        try:
            target(*args)
        except ImportCancelled:
            logger.info('Cancelled')
            self._new_status('cancelled')
        except Exception as e:
            if self._cancel.is_set():
                logger.info('Cancelled')
                self._new_status('cancelled')
            else:
                logger.error(f"{self._status.get('state')} failed: {e.__class__.__name__}: {e}")
                self._new_status('error', error=str(e), url=self._status.get('url'))

    def _check_cancel(self):
        if self._cancel.is_set():
            raise ImportCancelled()

    @plugs.tag
    def get_status(self) -> dict:
        """
        Current status (also published on ``ytimport.status``)::

            {'state': 'idle' | 'fetching' | 'info' | 'importing' | 'done' | 'cancelled' | 'error' | 'updating'
                      | 'updated',
             'url': ..., 'info': {...} (state 'info', see utils.build_info),
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

        :param url: Link to a video or a playlist (YouTube, YouTube Music, or any site yt-dlp supports)
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
        if not info['entries']:
            raise RuntimeError('No playable entries found')
        logger.info(f"Info loaded: {info['kind']} '{info['title']}' with {len(info['entries'])} entries")
        self._new_status('info', url=url, info=info)

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    @staticmethod
    def _library_path() -> str:
        return os.path.abspath(os.path.expanduser(components.player.get_music_library_path()))

    def _target_folder(self, name):
        folder = utils.sanitize_folder(name)
        if not folder:
            raise ValueError('Please enter a folder name')
        library = self._library_path()
        target = os.path.abspath(os.path.join(library, folder))
        if os.path.commonpath([library, target]) != library or target == library:
            raise ValueError(f"Invalid folder name: '{name}'")
        return folder, target

    @plugs.tag
    def check_folder(self, name: str) -> dict:
        """
        Folder name as it will be created and whether it exists already

        :return: ``{'folder': 'Max_uebernachtet_bei_Oma', 'exists': False}``
        """
        folder = utils.sanitize_folder(name)
        if not folder:
            return {'folder': '', 'exists': False}
        return {'folder': folder, 'exists': os.path.exists(os.path.join(self._library_path(), folder))}

    @plugs.tag
    def start_import(self, folder: str, tracks: list, artist: str = '', album: str = '', cover: bool = True) -> str:
        """
        Start the import in the background. Result: state 'done' (or 'error' / 'cancelled')

        :param folder: Name of the new folder in the music library (is cleaned, see utils.sanitize_folder).
            The folder must not exist yet
        :param tracks: ``[{url, title, start?, end?}]`` in the order of the folder; ``start``/``end`` in
            seconds cut a part (chapter) out of the video
        :param artist: Artist (and album artist) of all tracks
        :param album: Album of all tracks
        :param cover: Embed the thumbnail as cover
        :return: The folder name that is created
        """
        folder_name, target = self._target_folder(folder)
        if os.path.exists(target):
            raise FileExistsError(f"Folder '{folder_name}' exists already")
        tracks = utils.normalize_tracks(tracks)
        if not tracks:
            raise ValueError('No tracks selected')
        artist = str(artist or '').strip()
        album = str(album or '').strip()
        self._start_job('importing', self._job_import, folder_name, target, tracks, artist, album, bool(cover),
                        folder=folder_name, current=0, total=len(tracks), track_title='', phase='download',
                        percent=0, failed=[])
        return folder_name

    def _job_import(self, folder_name, target, tracks, artist, album, cover):
        os.makedirs(self._tmp_base, exist_ok=True)
        job_dir = tempfile.mkdtemp(prefix='job_', dir=self._tmp_base)
        try:
            self._import_tracks(job_dir, folder_name, target, tracks, artist, album, cover)
        finally:
            shutil.rmtree(job_dir, ignore_errors=True)

    def _import_tracks(self, job_dir, folder_name, target, tracks, artist, album, cover):
        src_dir = os.path.join(job_dir, 'src')
        out_dir = os.path.join(job_dir, folder_name)
        os.makedirs(src_dir)
        os.makedirs(out_dir)
        total = len(tracks)
        width = max(2, len(str(total)))
        # Index of the last track that needs a download: delete it afterwards to save space
        last_use = {track['url']: idx for idx, track in enumerate(tracks)}
        sources = {}
        failed = []
        logger.info(f"Import of {total} tracks into '{folder_name}'")

        for idx, track in enumerate(tracks):
            self._check_cancel()
            number = idx + 1
            self._set_status(force=True, current=number, track_title=track['title'], phase='download', percent=0)
            try:
                if track['url'] not in sources:
                    sources[track['url']] = self._download(track['url'], src_dir, number, cover)
                destination = os.path.join(out_dir, utils.track_filename(number, track['title'], width))
                self._import_track(sources[track['url']], destination, track, artist, album, number, total)
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
        self._finish(folder_name, out_dir, target)
        logger.info(f"Import into '{folder_name}' done ({total - len(failed)} of {total} tracks)")
        self._new_status('done', folder=folder_name, total=total, imported=total - len(failed), failed=failed)

    def _import_track(self, source, destination, track, artist, album, number, total):
        """Convert (or cut out) one track and write its tags"""
        self._check_cancel()
        self._set_status(force=True, phase='convert', percent=0)
        self._convert(source, destination, track['start'], track['end'])
        utils.tag_mp3(destination, track['title'], artist, album, number, total, source.get('cover'))

    def _finish(self, folder_name, out_dir, target):
        """Move the finished folder into the library, set the permissions, update the MPD database"""
        if os.path.exists(target):
            raise FileExistsError(f"Folder '{folder_name}' exists already")
        shutil.move(out_dir, target)
        with cfg:
            check_user_rights = cfg.getn('playermpd', 'library', 'check_user_rights', default=True)
        if check_user_rights is True:
            try:
                misc.recursive_chmod(target, mode_files=0o666, mode_dirs=0o777)
            except OSError as e:
                logger.warning(f"Could not set permissions of '{target}': {e}")
        # Not update_wait: that would block all other plugin calls (e.g. cards) while MPD scans
        plugs.call_ignore_errors('player', 'ctrl', 'update')

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
        return source

    def _read_cover(self, src_dir, name) -> Optional[bytes]:
        """Convert the downloaded thumbnail to a small JPEG and return its bytes (None if not available)"""
        thumbnails = [f for f in glob.glob(os.path.join(src_dir, f'{name}.*'))
                      if f.lower().endswith(THUMBNAIL_EXTENSIONS)]
        if not thumbnails:
            return None
        jpeg = os.path.join(src_dir, f'{name}_cover.jpg')
        result = subprocess.run(utils.ffmpeg_cover_cmd(self._ffmpeg, thumbnails[0], jpeg), shell=False,
                                check=False, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        for thumbnail in thumbnails:
            os.remove(thumbnail)
        if result.returncode != 0 or not os.path.exists(jpeg):
            logger.warning(f"Could not convert the thumbnail: {result.stderr.strip()}")
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
        """Convert to MP3 with ffmpeg, publishes the progress, can be cancelled"""
        cmd = utils.ffmpeg_convert_cmd(self._ffmpeg, source['audio'], destination, self._quality, start, end)
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
