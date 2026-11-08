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

// What the core expects in 'start_import'
const toImportTracks = (tracks) => (
  tracks
    .filter((track) => track.selected)
    .map(({ url, title, start, end }) => ({ url, title, start, end }))
);

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
  moveItem,
  toImportTracks,
};
