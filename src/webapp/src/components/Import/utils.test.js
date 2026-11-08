import { buildTracks, chaptersOf, formatDate, isBusy, moveItem, toImportTracks } from './utils';

const video = {
  kind: 'video',
  entries: [{
    url: 'https://y/v',
    title: 'Hörspiel',
    duration: 300,
    available: true,
    chapters: [
      { title: 'Teil 1', start: 0, end: 100 },
      { title: 'Teil 2', start: 100, end: 300 },
    ],
  }],
};

const playlist = {
  kind: 'playlist',
  entries: [
    { url: 'https://y/1', title: 'A', duration: 60, available: true, chapters: [] },
    { url: 'https://y/2', title: '[Private video]', duration: null, available: false, chapters: [] },
  ],
};

describe('import track list', () => {
  test('a video is one track, or one track per chapter', () => {
    expect(buildTracks(video, false)).toEqual([
      expect.objectContaining({ url: 'https://y/v', title: 'Hörspiel', start: null, end: null, selected: true }),
    ]);
    expect(buildTracks(video, true)).toEqual([
      expect.objectContaining({ title: 'Teil 1', start: 0, end: 100, duration: 100, selected: true }),
      expect.objectContaining({ title: 'Teil 2', start: 100, end: 300, duration: 200, selected: true }),
    ]);
    expect(chaptersOf(video)).toHaveLength(2);
  });

  test('unavailable playlist entries are not selected', () => {
    const tracks = buildTracks(playlist, true);
    expect(tracks.map((track) => track.selected)).toEqual([true, false]);
    expect(chaptersOf(playlist)).toEqual([]);
    expect(toImportTracks(tracks)).toEqual([{ url: 'https://y/1', title: 'A', start: null, end: null }]);
  });

  test('nothing of a podcast feed is selected, episodes keep their date', () => {
    const feed = {
      kind: 'feed',
      entries: [
        { url: 'https://cdn/2.mp3', title: 'Folge 2', duration: 3606, date: '2026-11-03', available: true, chapters: [] },
        { url: 'https://cdn/1.mp3', title: 'Folge 1', duration: null, date: null, available: true, chapters: [] },
      ],
    };
    const tracks = buildTracks(feed, true);
    expect(tracks.map((track) => [track.title, track.date, track.selected])).toEqual([
      ['Folge 2', '2026-11-03', false],
      ['Folge 1', null, false],
    ]);
    expect(toImportTracks(tracks)).toEqual([]);
  });

  test('formatDate', () => {
    expect(formatDate('2026-11-03', 'de')).toBe('3.11.2026');
    expect(formatDate(null, 'de')).toBeNull();
    expect(formatDate('kein Datum', 'de')).toBe('kein Datum');
  });

  test('keys are unique', () => {
    const keys = buildTracks(video, true).map((track) => track.key);
    expect(new Set(keys).size).toBe(keys.length);
  });

  test('moveItem', () => {
    expect(moveItem(['a', 'b', 'c'], 0, 1)).toEqual(['b', 'a', 'c']);
    expect(moveItem(['a', 'b', 'c'], 2, 1)).toEqual(['a', 'c', 'b']);
    expect(moveItem(['a', 'b', 'c'], 0, -1)).toEqual(['a', 'b', 'c']);
    expect(moveItem(['a', 'b', 'c'], 2, 3)).toEqual(['a', 'b', 'c']);
  });

  test('isBusy', () => {
    expect(isBusy({ state: 'importing' })).toBe(true);
    expect(isBusy({ state: 'info' })).toBe(false);
    expect(isBusy(undefined)).toBe(false);
  });
});
