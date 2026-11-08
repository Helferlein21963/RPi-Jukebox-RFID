"""
Helpers to rename folders and songs of the music library (used by the player's ``rename``).

Pure file system functions without a running jukebox: checking names, renaming, rewriting stored paths
(card database, remembered folder positions) and writing the title tag.
"""

import os
import re
from typing import Optional

#: Characters not allowed in names: on Linux ``/``, the rest for copies over Samba / to Windows
_FORBIDDEN_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')

NAME_MAX_LENGTH = 120


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
