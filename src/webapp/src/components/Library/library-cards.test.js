import { buildCardIndex } from './library-cards';

// No connection to the core in tests
jest.mock('../../utils/request', () => jest.fn());

const LIBRARY = '/home/pi/RPi-Jukebox-RFID/shared/audiofolders';

const card = (method, args, name) => ({
  action: { package: 'player', plugin: 'ctrl', method, args, kwargs: {} },
  ...(name !== undefined ? { name } : {}),
});

describe('buildCardIndex', () => {
  it('finds the cards of folders, songs and albums', () => {
    const index = buildCardIndex({
      '111': card('play_folder', [`${LIBRARY}/Bobo/`], 'Bobo'),
      '222': card('play_card', ['Bobo']),
      '333': card('play_single', ['Bobo/01.mp3'], 'Song'),
      '444': card('play_album', ['Artist', 'Album'], 'Album'),
      '555': card('toggle', []),
    }, LIBRARY);

    expect(index.folders.Bobo).toEqual([{ id: '111', name: 'Bobo' }, { id: '222', name: undefined }]);
    expect(index.songs['Bobo/01.mp3']).toEqual([{ id: '333', name: 'Song' }]);
    expect(index.albums[JSON.stringify(['Artist', 'Album'])]).toEqual([{ id: '444', name: 'Album' }]);
    expect(Object.keys(index.folders)).toEqual(['Bobo']);
  });

  it('sorts named cards first, alphabetically, then by ID', () => {
    const index = buildCardIndex({
      '20': card('play_folder', ['A']),
      '10': card('play_folder', ['A']),
      '30': card('play_folder', ['A'], 'zebra'),
      '40': card('play_folder', ['A'], 'Affe'),
    }, LIBRARY);

    expect(index.folders.A.map(({ id }) => id)).toEqual(['40', '30', '10', '20']);
  });

  it('copes with no cards', () => {
    expect(buildCardIndex(undefined, LIBRARY)).toEqual({ folders: {}, songs: {}, albums: {} });
  });
});
