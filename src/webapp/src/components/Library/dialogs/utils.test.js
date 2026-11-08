import { cleanName, renameErrorKey } from './utils';

describe('cleanName', () => {
  it.each([
    ['Max übernachtet bei Oma', 'Max übernachtet bei Oma'],
    ['  a   b  ', 'a b'],
    ['AC/DC: Best?', 'AC DC Best'],
    ['..hidden..', 'hidden'],
    ['', ''],
    [undefined, ''],
  ])('%s → %s', (name, expected) => {
    expect(cleanName(name)).toBe(expected);
  });
});

describe('renameErrorKey', () => {
  it.each([
    ["FileExistsError: 'Conni' already exists", 'library.rename.errors.exists'],
    ["ValueError: 'Conni' is being played. Stop the playback first.", 'library.rename.errors.playing'],
    ["ValueError: Invalid name: '..'", 'library.rename.errors.invalid-name'],
    ['PermissionError: denied', 'library.rename.errors.unknown'],
    [undefined, 'library.rename.errors.unknown'],
  ])('%s', (message, expected) => {
    expect(renameErrorKey(message)).toBe(expected);
  });
});
