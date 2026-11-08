// States of the core plugin 'ytimport' in which no other job can start
const BUSY_STATES = ['fetching', 'importing', 'updating'];

const isBusy = (status) => BUSY_STATES.includes(status?.state);

// Chapters of a single video (a playlist is listed flat, without chapters)
const chaptersOf = (info) => (
  info?.kind === 'video' ? (info.entries[0]?.chapters || []) : []
);

// The editable track list: one track per playlist entry,
// or one per chapter when a video is split into its chapters
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
      available: entry.available,
      selected: entry.available,
    }];
  })
);

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
  isBusy,
  moveItem,
  toImportTracks,
};
