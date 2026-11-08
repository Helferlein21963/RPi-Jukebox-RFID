import { cardMusic } from './card-music';
import { coverRequest } from './card-cover';

// No connection to the core in tests
jest.mock('../../utils/request', () => jest.fn());

const LIBRARY = '/home/pi/RPi-Jukebox-RFID/shared/audiofolders';

const card = (method, args, extra = {}) => ({
  action: { package: 'player', plugin: 'ctrl', method, args, kwargs: {} },
  ...extra,
});

describe('cardMusic', () => {
  it('reads folders relative to the library', () => {
    expect(cardMusic(card('play_folder', [`${LIBRARY}/Bobo/`]), LIBRARY)).toEqual({ folder: 'Bobo' });
    expect(cardMusic(card('play_card', ['Bobo']), LIBRARY)).toEqual({ folder: 'Bobo' });
    expect(cardMusic(card('play_folder', ['../../shared/audiofolders/Bobo']), LIBRARY)).toEqual({ folder: 'Bobo' });
  });

  it('reads keyword arguments', () => {
    const kwargsCard = { action: { package: 'player', plugin: 'ctrl', method: 'play_folder', kwargs: { folder: 'Bobo' } } };
    expect(cardMusic(kwargsCard, LIBRARY)).toEqual({ folder: 'Bobo' });
  });

  it('reads songs and albums', () => {
    expect(cardMusic(card('play_single', ['Bobo/01.mp3']), LIBRARY)).toEqual({ song: 'Bobo/01.mp3' });
    expect(cardMusic(card('play_album', ['Artist', 'Album']), LIBRARY))
      .toEqual({ albumartist: 'Artist', album: 'Album' });
  });

  it('ignores cards that do not start music', () => {
    expect(cardMusic(card('toggle', []), LIBRARY)).toBeUndefined();
    expect(cardMusic({ action: { package: 'volume', plugin: 'ctrl', method: 'change_volume', args: [5] } }, LIBRARY))
      .toBeUndefined();
    expect(cardMusic(undefined, LIBRARY)).toBeUndefined();
  });
});

describe('coverRequest', () => {
  it('asks for the cover of the folder, song or album', () => {
    expect(coverRequest({ folder: 'Bobo' })).toEqual(['getFolderCoverArt', { folder: 'Bobo' }]);
    expect(coverRequest({ song: 'Bobo/01.mp3' })).toEqual(['getSingleCoverArt', { song_url: 'Bobo/01.mp3' }]);
    expect(coverRequest({ albumartist: 'Artist', album: 'Album' }))
      .toEqual(['getAlbumCoverArt', { albumartist: 'Artist', album: 'Album' }]);
  });

  it('asks for nothing for cards without music', () => {
    expect(coverRequest(undefined)).toBeUndefined();
  });
});
