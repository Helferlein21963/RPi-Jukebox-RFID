// Sorting of the library views. Only the display changes: a folder still plays in the order of its file names.

// The sorts each view offers, the first one is the default
const SORTS = {
  folders: ['name-asc', 'name-desc', 'recent'],
  albums: ['name-asc', 'name-desc', 'artist', 'recent'],
  songs: ['name-asc', 'name-desc', 'artist', 'recent'],
};

const STORAGE_KEY = 'librarySort';

// The chosen sort of each view, e.g. { folders: 'recent' }. Storage can be unavailable (private mode)
const loadSorts = () => {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    return stored && typeof stored === 'object' ? stored : {};
  } catch (e) {
    return {};
  }
};

const saveSorts = (sorts) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sorts));
  } catch (e) {
    // Then the sort is only kept until the page is loaded again
  }
};

const sortOf = (sorts, view) => (
  SORTS[view]?.includes(sorts?.[view]) ? sorts[view] : SORTS[view]?.[0]
);

// Natural order, ignoring case and accents: 'Folge 2' before 'Folge 10', 'ä' next to 'a'
const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });
const compareText = (a, b) => collator.compare(a || '', b || '');

// Newest first; entries without a date at the end. Dates are numbers or ISO strings
const compareRecent = (a, b) => {
  if (a === b) return 0;
  if (a === null || a === undefined || a === '') return 1;
  if (b === null || b === undefined || b === '') return -1;
  return a < b ? 1 : -1;
};

// Several comparisons: the next one decides when the first ones are equal
const by = (...comparisons) => (a, b) => {
  for (const compare of comparisons) {
    const result = compare(a, b);
    if (result !== 0) return result;
  }
  return 0;
};

// Content of a folder: the subfolders first, then the songs (and streams), each part sorted.
// Songs come in play order from the core: that is their A–Z, so the default shows them as they are played
const sortFolders = (entries, sort) => {
  const folders = entries.filter((entry) => entry.type === 'directory');
  const others = entries.filter((entry) => entry.type !== 'directory');
  const byName = (a, b) => compareText(a.name, b.name);
  const compareFolders = {
    'name-asc': byName,
    'name-desc': (a, b) => byName(b, a),
    recent: by((a, b) => compareRecent(a.modified, b.modified), byName),
  }[sort] || byName;
  const playOrder = new Map(others.map((entry, idx) => [entry, idx]));
  const byPlayOrder = (a, b) => playOrder.get(a) - playOrder.get(b);
  const compareOthers = {
    'name-desc': (a, b) => byPlayOrder(b, a),
    recent: by((a, b) => compareRecent(a.modified, b.modified), byPlayOrder),
  }[sort];
  return [
    ...[...folders].sort(compareFolders),
    ...(compareOthers ? [...others].sort(compareOthers) : others),
  ];
};

const albumKey = ({ albumartist, album }) => `${albumartist || ''}\u0000${album || ''}`;

// Date of an album: its newest song ({ key: date })
const albumDates = (songs) => songs.reduce((dates, song) => {
  const key = albumKey(song);
  if (song.modified && compareRecent(song.modified, dates[key]) < 0) dates[key] = song.modified;
  return dates;
}, {});

const sortAlbums = (albums, sort, dates = {}) => {
  const byAlbum = (a, b) => compareText(a.album, b.album);
  const byArtist = (a, b) => compareText(a.albumartist, b.albumartist);
  const compare = {
    'name-asc': by(byAlbum, byArtist),
    'name-desc': by((a, b) => byAlbum(b, a), byArtist),
    artist: by(byArtist, byAlbum),
    recent: by((a, b) => compareRecent(dates[albumKey(a)], dates[albumKey(b)]), byAlbum),
  }[sort];
  return compare ? [...albums].sort(compare) : albums;
};

const songName = (song) => song.title || (song.file || '').split('/').pop();

const sortSongs = (songs, sort) => {
  const byName = (a, b) => compareText(songName(a), songName(b));
  const compare = {
    'name-asc': byName,
    'name-desc': (a, b) => byName(b, a),
    artist: by((a, b) => compareText(a.artist, b.artist), byName),
    recent: by((a, b) => compareRecent(a.modified, b.modified), byName),
  }[sort];
  return compare ? [...songs].sort(compare) : songs;
};

export {
  albumDates,
  compareRecent,
  compareText,
  loadSorts,
  saveSorts,
  sortAlbums,
  sortFolders,
  sortOf,
  sortSongs,
  SORTS,
};
