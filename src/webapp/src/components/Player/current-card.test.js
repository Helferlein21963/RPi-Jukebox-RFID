import { findCurrentCard } from './current-card';

// No connection to the core in tests
jest.mock('../../utils/request', () => jest.fn());

const LIBRARY = '/home/pi/RPi-Jukebox-RFID/shared/audiofolders';

const card = (method, args, extra = {}) => ({
  action: { package: 'player', plugin: 'ctrl', method, args, kwargs: {} },
  ...extra,
});

const playing = (file, album = '', albumartist = '') => ({
  isActive: true, isPlaying: true, file, album, albumartist,
});

describe('findCurrentCard', () => {
  const cardsList = {
    '111': card('play_folder', ['Hoerspiele'], { name: 'Alle Hörspiele' }),
    '222': card('play_folder', ['Hoerspiele/Bobo']),
    '333': card('play_folder', ['Hoerspiele/Bobo'], { name: 'Bobo' }),
    '444': card('toggle', []),
    '555': card('play_album', ['Artist', 'Album'], { name: 'Album' }),
  };
  const nowPlaying = playing('Hoerspiele/Bobo/01.mp3');

  it('takes the swiped card if it plays the current song', () => {
    expect(findCurrentCard({ cardsList, swipedCardId: '222', nowPlaying, libraryPath: LIBRARY }))
      .toEqual({ id: '222', name: undefined });
    expect(findCurrentCard({ cardsList, swipedCardId: '111', nowPlaying, libraryPath: LIBRARY }))
      .toEqual({ id: '111', name: 'Alle Hörspiele' });
  });

  it('otherwise takes the most specific card, named ones first', () => {
    expect(findCurrentCard({ cardsList, swipedCardId: '444', nowPlaying, libraryPath: LIBRARY }))
      .toEqual({ id: '333', name: 'Bobo' });
    expect(findCurrentCard({ cardsList, swipedCardId: undefined, nowPlaying, libraryPath: LIBRARY }))
      .toEqual({ id: '333', name: 'Bobo' });
  });

  it('matches albums', () => {
    expect(findCurrentCard({
      cardsList, swipedCardId: '555', nowPlaying: playing('Other/01.mp3', 'Album', 'Artist'), libraryPath: LIBRARY,
    })).toEqual({ id: '555', name: 'Album' });
  });

  it('returns nothing without a matching card or playback', () => {
    expect(findCurrentCard({ cardsList, nowPlaying: playing('Musik/01.mp3'), libraryPath: LIBRARY })).toBeUndefined();
    expect(findCurrentCard({ cardsList, nowPlaying: { isActive: false }, libraryPath: LIBRARY })).toBeUndefined();
    expect(findCurrentCard({ cardsList: undefined, nowPlaying, libraryPath: LIBRARY })).toBeUndefined();
  });

  it('does not match folders with the same prefix', () => {
    const list = { '1': card('play_folder', ['Hoerspiele/Bob']) };
    expect(findCurrentCard({ cardsList: list, nowPlaying, libraryPath: LIBRARY })).toBeUndefined();
  });
});
