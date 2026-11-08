import { toLibraryPath } from '../Library/now-playing';
import { DEFAULT_AUDIO_DIR } from '../../config';

// Folders inside the music library are shown relative to it
const toDisplayPath = (path, libraryPath) => (
  typeof path === 'string'
    ? toLibraryPath(path, libraryPath).replace(`${DEFAULT_AUDIO_DIR}/`, '')
    : path
);

// Paths relative to the music library, like the files of the player status
const toRelativePath = (path, libraryPath) => (
  toDisplayPath(path, libraryPath).replace(/^\.\//, '').replace(/\/+$/, '')
);

/**
 * The music a card plays: { folder }, { song } or { albumartist, album }, with paths relative to the library.
 * undefined for cards that don't start music (e.g. volume or toggle cards).
 */
const cardMusic = (card, libraryPath) => {
  const { package: pkg, plugin, method, args, kwargs } = card?.action || {};
  if (pkg !== 'player' || plugin !== 'ctrl') return undefined;

  const arg = (index, key) => (Array.isArray(args) ? args[index] : undefined) ?? kwargs?.[key];
  const text = (value) => (typeof value === 'string' ? value : undefined);

  switch (method) {
    case 'play_folder':
    case 'play_card': {
      const folder = text(arg(0, 'folder'));
      return folder ? { folder: toRelativePath(folder, libraryPath) } : undefined;
    }
    case 'play_single': {
      const song = text(arg(0, 'song_url'));
      return song ? { song: toRelativePath(song, libraryPath) } : undefined;
    }
    case 'play_album': {
      const album = text(arg(1, 'album'));
      return album ? { albumartist: text(arg(0, 'albumartist')) || '', album } : undefined;
    }
    default:
      return undefined;
  }
};

export {
  cardMusic,
  toDisplayPath,
};
