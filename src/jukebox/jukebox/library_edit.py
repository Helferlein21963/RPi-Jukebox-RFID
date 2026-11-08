"""
Helpers to rename folders and songs of the music library and to change the order of a folder
(used by the player's ``rename`` and ``reorder``), and to find the neighbor of a folder (``play_next_folder``).

Pure file system functions without a running jukebox: checking names, renaming, rewriting stored paths
(card database, remembered folder positions) and writing the title and track number tags.
"""

import os
import re
from typing import Callable, List, Optional, Sequence, Tuple

#: Characters not allowed in names: on Linux ``/``, the rest for copies over Samba / to Windows
_FORBIDDEN_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')

NAME_MAX_LENGTH = 120

#: Leading number of a file name (``07 - Title.mp3``)
NUMBER_RE = re.compile(r'^(\d+)')
#: Leading number with its separator: ``07 - ``, ``07_``, ``07.``, ``07) ``, ``07 ``
_NUMBER_PREFIX_RE = re.compile(r'^\d+(?:\s*[-_.)]+\s*|\s+)')

#: Files that set the content of their folder themselves: the order of such a folder is not set by file names
SPECIAL_FILES = ('livestream.txt', 'podcast.txt', '.m3u')


def clean_name(name: str) -> str:
    """
    Check and clean a new file or folder name.

    Umlauts and spaces are allowed. Forbidden characters (``\\ / : * ? " < > |``, control characters) become
    spaces, repeated spaces one, dots and spaces at the edges are removed.

    :raises ValueError: if nothing usable is left
    """
    cleaned = _FORBIDDEN_RE.sub(' ', str(name or ''))
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' .')
    cleaned = cleaned[:NAME_MAX_LENGTH].rstrip(' .')
    if not cleaned:
        raise ValueError(f"Invalid name: '{name}'")
    return cleaned


def resolve_in_library(library: str, path: str) -> str:
    """
    Absolute path of an existing entry of the music library.

    :param library: Absolute path of the music library
    :param path: Absolute path, or relative to the library
    :raises ValueError: if the path is the library itself or outside of it
    :raises FileNotFoundError: if it does not exist
    """
    library = os.path.abspath(library)
    # No realpath: symlinked folders inside the library stay allowed
    target = os.path.abspath(os.path.join(library, path))
    if os.path.commonpath([library, target]) != library or target == library:
        raise ValueError(f"'{path}' is not inside the music library")
    if not os.path.lexists(target):
        raise FileNotFoundError(f"'{path}' does not exist")
    return target


def neighbor_folder(library: str, folder: str, step: int,
                    is_playable: Optional[Callable[[str], bool]] = None) -> Optional[str]:
    """
    The next (``step=1``) or previous (``step=-1``) folder next to ``folder``, in the same parent folder.

    Folders are in alphabetical order (case-insensitive, like the playlist generator and the library); after the
    last one comes the first again. Hidden folders (``.name``) and folders ``is_playable`` rejects (e.g. empty
    ones) are skipped. ``folder`` itself need not exist any more (e.g. renamed): its name still sets the position.

    :param library: Absolute path of the music library
    :param folder: Absolute path, or relative to the library
    :param step: 1 for the next folder, -1 for the previous one
    :param is_playable: Check for a candidate (absolute path); default: every folder
    :return: Absolute path of the neighbor, or None if there is no other (playable) folder
    :raises ValueError: if the folder is the library itself or outside of it
    """
    library = os.path.abspath(library)
    target = os.path.abspath(os.path.join(library, folder))
    if os.path.commonpath([library, target]) != library or target == library:
        raise ValueError(f"'{folder}' is not inside the music library")
    parent, name = os.path.split(target)
    names = [entry.name for entry in os.scandir(parent)
             if entry.is_dir(follow_symlinks=True) and not entry.name.startswith('.')]
    if name not in names:
        names.append(name)
    names.sort(key=lambda n: (n.casefold(), n))
    pos = names.index(name)
    for i in range(1, len(names)):
        candidate = os.path.join(parent, names[(pos + step * i) % len(names)])
        if is_playable is None or is_playable(candidate):
            return candidate
    return None


def new_path(old: str, new_name: str) -> str:
    """
    Path of ``old`` after renaming it to ``new_name`` (in the same folder).

    Files keep their extension: ``new_name`` is the name without it (an extension typed anyway is not doubled).

    :raises ValueError: if the name is invalid
    """
    name = clean_name(new_name)
    if not os.path.isdir(old):
        extension = os.path.splitext(old)[1]
        if extension and name.lower().endswith(extension.lower()):
            name = clean_name(name[:-len(extension)])
        name += extension
    return os.path.join(os.path.dirname(old), name)


def rename_entry(old: str, new_name: str) -> str:
    """
    Rename a file or folder in its folder.

    A change of upper / lower case only works also on case-insensitive file systems.

    :param old: Absolute path
    :param new_name: New name, for files without extension (see :func:`new_path`)
    :return: The new absolute path (unchanged if the name is the same)
    :raises FileExistsError: if an entry with the new name exists
    """
    target = new_path(old, new_name)
    if target == old:
        return old
    same_entry = os.path.normcase(target) == os.path.normcase(old)
    if os.path.lexists(target) and not same_entry:
        raise FileExistsError(f"'{os.path.basename(target)}' already exists")
    if same_entry:
        temp = f'{old}.renaming'
        os.rename(old, temp)
        os.rename(temp, target)
    else:
        os.rename(old, target)
    return target


def rewrite_path(value, old: str, new: str, library: str) -> Optional[str]:
    """
    ``value`` after ``old`` was renamed to ``new``, None if it is not affected.

    Affected are ``old`` itself and everything inside it. ``value`` stays absolute or relative to the library,
    like it was. URLs and non-strings are never affected.

    :param value: e.g. a folder of a card, a song URL
    :param old: Absolute path before renaming
    :param new: Absolute path after renaming
    :param library: Absolute path of the music library
    """
    if not isinstance(value, str) or not value or '://' in value:
        return None
    is_absolute = os.path.isabs(value)
    full = os.path.normpath(value if is_absolute else os.path.join(library, value))
    old = os.path.normpath(old)
    if full != old and not full.startswith(old + os.sep):
        return None
    moved = os.path.normpath(new) + full[len(old):]
    return moved if is_absolute else os.path.relpath(moved, library)


def title_supported() -> bool:
    """True if title tags can be written (mutagen is installed, e.g. by the YouTube import)"""
    try:
        import mutagen  # noqa: F401
    except ImportError:
        return False
    return True


def set_title(path: str, title: str) -> None:
    """
    Write the title tag of a song (MP3, FLAC, Ogg, M4A, ... — every format mutagen knows).

    :raises ValueError: if the file has no tag format mutagen can write
    :raises ImportError: if mutagen is not installed
    """
    import mutagen

    audio = mutagen.File(path, easy=True)
    if audio is None:
        raise ValueError(f"Can't write tags of '{os.path.basename(path)}'")
    if audio.tags is None:
        audio.add_tags()
    audio['title'] = [title]
    audio.save()


def rewrite_path_many(value, renames: Sequence[Tuple[str, str]], library: str) -> Optional[str]:
    """
    ``value`` after several entries were renamed at once (e.g. the files of a folder that swap names),
    None if it is not affected.

    Unlike calling :func:`rewrite_path` one after the other, a value is moved once only: with ``a → b`` and
    ``b → a``, ``a`` becomes ``b`` (and not ``a`` again).

    :param renames: ``(old, new)`` absolute paths
    """
    for old, new in renames:
        moved = rewrite_path(value, old, new, library)
        if moved is not None:
            return moved
    return None


def track_number(filename: str) -> Optional[int]:
    """The number a file name starts with (``07 - Title.mp3`` → 7), None if it has none"""
    match = NUMBER_RE.match(filename)
    return int(match.group(1)) if match else None


def strip_number(stem: str) -> str:
    """Title part of a file name without its leading number: ``07 - Title`` → ``Title``"""
    stripped = _NUMBER_PREFIX_RE.sub('', stem, count=1).strip()
    return stripped or stem


def is_special_file(filename: str) -> bool:
    """True for a file that sets the content of its folder (livestream, podcast, M3U playlist)"""
    return filename.casefold().endswith(SPECIAL_FILES)


def reorder_names(files: Sequence[str]) -> List[str]:
    """
    New names of the files of a folder in the order given: ``01 - Title.mp3``, ``02 - ...``.

    The old leading number is dropped, the extension stays. The folder is played in alphabetical order, so the
    numbers (with leading zeros) set the play order.
    """
    width = max(2, len(str(len(files))))
    names = []
    for idx, filename in enumerate(files):
        stem, extension = os.path.splitext(filename)
        try:
            title = clean_name(strip_number(stem))
        except ValueError:
            title = 'Track'
        names.append(f'{idx + 1:0{width}d} - {title}{extension}')
    return names


def rename_files(folder: str, renames: Sequence[Tuple[str, str]]) -> None:
    """
    Rename files of one folder at once, also when they swap their names.

    First every file gets a temporary name, then its new one. If something fails, the files get their old names
    back as far as possible.

    :param folder: Absolute path of the folder
    :param renames: ``(old name, new name)``, names without path
    :raises FileExistsError: if a new name is taken by a file that is not renamed
    """
    renames = [(old, new) for old, new in renames if old != new]
    leaving = {old.casefold() for old, _ in renames}
    for _, new in renames:
        if os.path.lexists(os.path.join(folder, new)) and new.casefold() not in leaving:
            raise FileExistsError(f"'{new}' already exists")

    done = []
    try:
        for idx, (old, new) in enumerate(renames):
            temp = os.path.join(folder, f'.reorder_{idx}{os.path.splitext(old)[1]}')
            os.rename(os.path.join(folder, old), temp)
            done.append((old, temp, None))
        for idx, (old, temp, _) in enumerate(done):
            new = renames[idx][1]
            os.rename(temp, os.path.join(folder, new))
            done[idx] = (old, temp, new)
    except OSError:
        for old, temp, new in reversed(done):
            current = os.path.join(folder, new) if new else temp
            try:
                os.rename(current, os.path.join(folder, old))
            except OSError:
                pass
        raise


def set_track_number(path: str, number: int, total: int) -> bool:
    """
    Write the track number (``3/12``) of a song; the other tags stay, MP3 files keep their ID3 version.

    The modification time moves on by one second only: sorting by date keeps the order of the files, and MPD
    still notices the change (it reads the tags again when the time differs).

    :return: False if it could not be written (mutagen missing, file without a tag format)
    """
    if not title_supported():
        return False
    import mutagen

    stat = os.stat(path)
    try:
        if path.casefold().endswith('.mp3'):
            from mutagen.id3 import ID3, ID3NoHeaderError, TRCK
            try:
                tags = ID3(path)
                version = 3 if tags.version[:2] == (2, 3) else 4
            except ID3NoHeaderError:
                tags, version = ID3(), 3
            tags.setall('TRCK', [TRCK(encoding=3, text=f'{number}/{total}')])
            tags.save(path, v2_version=version)
        else:
            audio = mutagen.File(path, easy=True)
            if audio is None:
                return False
            if audio.tags is None:
                audio.add_tags()
            audio['tracknumber'] = [f'{number}/{total}']
            audio.save()
    except (mutagen.MutagenError, OSError, KeyError, ValueError):
        return False
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    return True
