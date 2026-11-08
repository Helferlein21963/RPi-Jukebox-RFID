// Same rules as jukebox.library_edit.clean_name in the core: the name the entry will get
const FORBIDDEN_CHARACTERS = /[\\/:*?"<>|]/g;

const cleanName = (name = '') => (
  Array.from(name, (char) => (char.charCodeAt(0) < 32 ? ' ' : char)).join('')
    .replace(FORBIDDEN_CHARACTERS, ' ')
    .replace(/\s+/g, ' ')
    .replace(/^[ .]+|[ .]+$/g, '')
);

// Translation key for an error message of the core (e.g. 'FileExistsError: ...')
const renameErrorKey = (message = '') => {
  const text = String(message);
  if (text.startsWith('FileExistsError')) return 'library.rename.errors.exists';
  if (text.includes('is being played')) return 'library.rename.errors.playing';
  if (text.includes('Invalid name')) return 'library.rename.errors.invalid-name';
  return 'library.rename.errors.unknown';
};

// Same rules as jukebox.library_edit (track_number / strip_number / reorder_names)
const NAME_MAX_LENGTH = 120;

const trackNumber = (name = '') => {
  const match = /^(\d+)/.exec(name);
  return match ? Number(match[1]) : null;
};

const stripNumber = (stem) => stem.replace(/^\d+(?:\s*[-_.)]+\s*|\s+)/, '').trim() || stem;

const splitExtension = (file) => {
  const dot = file.lastIndexOf('.');
  return dot > 0 ? [file.slice(0, dot), file.slice(dot)] : [file, ''];
};

// New names of the files of a folder in this order: '01 - Title.mp3', '02 - ...'
const reorderNames = (files) => {
  const width = Math.max(2, String(files.length).length);
  return files.map((file, idx) => {
    const [stem, extension] = splitExtension(file);
    const title = cleanName(Array.from(cleanName(stripNumber(stem))).slice(0, NAME_MAX_LENGTH).join('')) || 'Track';
    return `${String(idx + 1).padStart(width, '0')} - ${title}${extension}`;
  });
};

// Translation key for an error of the core when changing the order
const reorderErrorKey = (message = '') => {
  const text = String(message);
  if (text.includes('is being played')) return 'library.rename.errors.playing';
  if (text.includes('playlist or stream file')) return 'library.reorder.errors.special';
  if (text.includes('have changed')) return 'library.reorder.errors.changed';
  return 'library.reorder.errors.unknown';
};

export {
  cleanName,
  renameErrorKey,
  reorderErrorKey,
  reorderNames,
  stripNumber,
  trackNumber,
};
