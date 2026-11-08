// States of the core plugin 'ytimport' in which no other job can start
const BUSY_STATES = ['fetching', 'importing', 'updating'];

const isBusy = (status) => BUSY_STATES.includes(status?.state);

// Chapters of a single video (a playlist is listed flat, without chapters)
const chaptersOf = (info) => (
  info?.kind === 'video' ? (info.entries[0]?.chapters || []) : []
);

// The editable track list: one track per playlist entry,
// or one per chapter when a video is split into its chapters.
// Nothing of a podcast feed is selected: it often lists many long episodes
const buildTracks = (info, splitChapters) => (
  (info?.entries || []).flatMap((entry, idx) => {
    if (splitChapters && entry.chapters?.length > 1) {
      return entry.chapters.map((chapter, chapterIdx) => ({
        key: `${idx}-${chapterIdx}`,
        url: entry.url,
        title: chapter.title,
        start: chapter.start,
        end: chapter.end,
        duration: chapter.end - chapter.start,
        available: true,
        selected: true,
      }));
    }

    return [{
      key: `${idx}`,
      url: entry.url,
      title: entry.title,
      start: null,
      end: null,
      duration: entry.duration,
      date: entry.date || null,
      available: entry.available,
      selected: entry.available && info.kind !== 'feed',
    }];
  })
);

// Date of a podcast episode ('2026-11-03') in the language of the web app
const formatDate = (date, language) => {
  if (!date) return null;
  const parsed = new Date(`${date}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? date : parsed.toLocaleDateString(language);
};

// The tracks to import, without the files of the folder
const newTracks = (tracks) => tracks.filter((track) => !track.existing);

// The files of an existing folder (in play order) before the new tracks, to set the order of the whole folder
const mergeTracks = (existing, tracks) => [
  ...(existing || []).map(({ file, title }) => ({
    key: `file:${file}`,
    file,
    title,
    existing: true,
    available: true,
    selected: true,
  })),
  ...newTracks(tracks),
];

// What the core expects in 'start_import'.
// With 'reorder' the whole folder in the new order: {file} for a file that is in the folder already
const toImportTracks = (tracks, reorder = false) => (
  tracks
    .filter((track) => track.selected && (reorder || !track.existing))
    .map(({ file, existing, url, title, start, end }) => (
      existing ? { file } : { url, title, start, end }
    ))
);

// File names as the core makes them (preview only, the core decides):
// same rules as safe_filename / strip_number / plan_reorder_names in components/ytimport/utils.py
const FILENAME_MAX_LENGTH = 100;

const trimChars = (text, chars) => {
  let start = 0;
  let end = text.length;
  while (start < end && chars.includes(text[start])) start += 1;
  while (end > start && chars.includes(text[end - 1])) end -= 1;
  return text.slice(start, end);
};

const safeFilename = (title) => {
  // eslint-disable-next-line no-control-regex
  let name = String(title ?? '').replace(/[\\/:*?"<>|\x00-\x1f]/g, ' ');
  name = trimChars(name.replace(/\s+/g, ' '), ' .');
  // Characters, not UTF-16 units, like Python
  name = trimChars(Array.from(name).slice(0, FILENAME_MAX_LENGTH).join(''), ' .');
  return name || 'Track';
};

const stripNumber = (stem) => stem.replace(/^\d+(?:\s*[-_.)]+\s*|\s+)/, '').trim() || stem;

const splitExtension = (file) => {
  const dot = file.lastIndexOf('.');
  return dot > 0 ? [file.slice(0, dot), file.slice(dot)] : [file, ''];
};

// New file names when the order of the whole folder is set: {key: '01 - Title.mp3'}.
// Deselected new tracks are not imported and get no name
const reorderNames = (tracks) => {
  const items = tracks.filter((track) => track.existing || track.selected);
  const width = Math.max(2, String(items.length).length);
  return Object.fromEntries(items.map((track, idx) => {
    let [title, extension] = [track.title, '.mp3'];
    if (track.existing) {
      const [stem, ext] = splitExtension(track.file);
      [title, extension] = [stripNumber(stem), ext];
    }
    const number = String(idx + 1).padStart(width, '0');
    return [track.key, `${number} - ${safeFilename(title)}${extension}`];
  }));
};

const moveItem = (list, from, to) => {
  if (to < 0 || to >= list.length) return list;
  const result = [...list];
  const [item] = result.splice(from, 1);
  result.splice(to, 0, item);
  return result;
};

export {
  buildTracks,
  chaptersOf,
  formatDate,
  isBusy,
  mergeTracks,
  moveItem,
  newTracks,
  reorderNames,
  safeFilename,
  stripNumber,
  toImportTracks,
};
