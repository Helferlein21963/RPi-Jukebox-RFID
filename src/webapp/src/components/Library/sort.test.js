import {
  albumDates,
  loadSorts,
  saveSorts,
  sortAlbums,
  sortFolders,
  sortOf,
  sortSongs,
} from './sort';

describe('library sort', () => {
  const entries = [
    { type: 'directory', name: 'Folge 10', modified: 300 },
    { type: 'directory', name: 'äffle', modified: null },
    { type: 'directory', name: 'Folge 2', modified: 500 },
    { type: 'file', name: 'b.mp3', modified: 900 },
    { type: 'file', name: 'a.mp3', modified: 100 },
  ];
  const names = (list) => list.map(({ name }) => name);

  test('folders: subfolders first, then the songs; A–Z of the songs is their play order', () => {
    // The songs come in play order from the core (here: b before a)
    expect(names(sortFolders(entries, 'name-asc'))).toEqual(['äffle', 'Folge 2', 'Folge 10', 'b.mp3', 'a.mp3']);
    expect(names(sortFolders(entries, 'name-desc'))).toEqual(['Folge 10', 'Folge 2', 'äffle', 'a.mp3', 'b.mp3']);
    // Newest first, without a date at the end
    expect(names(sortFolders(entries, 'recent'))).toEqual(['Folge 2', 'Folge 10', 'äffle', 'b.mp3', 'a.mp3']);
    expect(entries[0].name).toBe('Folge 10');
  });

  test('songs of a folder by date, equal dates in play order', () => {
    const songs = [
      { type: 'file', name: '01.mp3', modified: 100 },
      { type: 'file', name: '02.mp3', modified: 300 },
      { type: 'file', name: '03.mp3', modified: 100 },
      { type: 'file', name: '04.mp3', modified: null },
    ];
    expect(names(sortFolders(songs, 'recent'))).toEqual(['02.mp3', '01.mp3', '03.mp3', '04.mp3']);
  });

  test('albums by name, artist or their newest song', () => {
    const albums = [
      { albumartist: 'Zoe', album: 'Bär' },
      { albumartist: 'Anna', album: 'Zirkus' },
      { albumartist: 'Anna', album: 'Apfel' },
    ];
    const label = (list) => list.map(({ albumartist, album }) => `${albumartist}/${album}`);
    expect(label(sortAlbums(albums, 'name-asc'))).toEqual(['Anna/Apfel', 'Zoe/Bär', 'Anna/Zirkus']);
    expect(label(sortAlbums(albums, 'name-desc'))).toEqual(['Anna/Zirkus', 'Zoe/Bär', 'Anna/Apfel']);
    expect(label(sortAlbums(albums, 'artist'))).toEqual(['Anna/Apfel', 'Anna/Zirkus', 'Zoe/Bär']);

    const dates = albumDates([
      { albumartist: 'Anna', album: 'Zirkus', modified: '2026-01-01T00:00:00Z' },
      { albumartist: 'Anna', album: 'Zirkus', modified: '2026-11-01T00:00:00Z' },
      { albumartist: 'Zoe', album: 'Bär', modified: '2026-05-01T00:00:00Z' },
    ]);
    expect(dates['Anna\u0000Zirkus']).toBe('2026-11-01T00:00:00Z');
    expect(label(sortAlbums(albums, 'recent', dates))).toEqual(['Anna/Zirkus', 'Zoe/Bär', 'Anna/Apfel']);
  });

  test('songs by title (or file name), artist or date', () => {
    const songs = [
      { file: 'x/zebra.mp3', title: 'Zebra', artist: 'Anna', modified: '2026-01-01T00:00:00Z' },
      { file: 'y/Banane.mp3', title: '', artist: 'Bert', modified: '2026-03-01T00:00:00Z' },
      { file: 'z/a.mp3', title: 'Apfel', artist: 'Bert', modified: '' },
    ];
    const files = (list) => list.map(({ file }) => file);
    expect(files(sortSongs(songs, 'name-asc'))).toEqual(['z/a.mp3', 'y/Banane.mp3', 'x/zebra.mp3']);
    expect(files(sortSongs(songs, 'name-desc'))).toEqual(['x/zebra.mp3', 'y/Banane.mp3', 'z/a.mp3']);
    expect(files(sortSongs(songs, 'artist'))).toEqual(['x/zebra.mp3', 'z/a.mp3', 'y/Banane.mp3']);
    expect(files(sortSongs(songs, 'recent'))).toEqual(['y/Banane.mp3', 'x/zebra.mp3', 'z/a.mp3']);
  });

  test('the chosen sort is kept in the browser', () => {
    localStorage.clear();
    expect(loadSorts()).toEqual({});
    expect(sortOf({}, 'albums')).toBe('name-asc');

    saveSorts({ songs: 'artist', folders: 'nonsense' });
    const sorts = loadSorts();
    expect(sortOf(sorts, 'songs')).toBe('artist');
    // Unknown values fall back to the default
    expect(sortOf(sorts, 'folders')).toBe('name-asc');

    localStorage.setItem('librarySort', 'not json');
    expect(loadSorts()).toEqual({});
  });
});
