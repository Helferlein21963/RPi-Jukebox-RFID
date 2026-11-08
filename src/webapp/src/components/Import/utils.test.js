import { buildTracks, chaptersOf, isBusy, moveItem, toImportTracks } from './utils';

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
