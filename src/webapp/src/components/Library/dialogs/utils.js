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

export {
  cleanName,
  renameErrorKey,
};
