import { tagFromUrl, tagToUrl } from './utils';

describe('album tags in URLs', () => {
  test.each([
    'Peppa Pig / Peppa Wutz - Hörspiele',
    '100% Kinderlieder',
    '_starts with underscore',
    ' ',
  ])('%p survives the round trip', (tag) => {
    expect(tagFromUrl(tagToUrl(tag))).toBe(tag);
  });

  test('an empty tag becomes a non-empty URL segment', () => {
    expect(tagToUrl('')).toBe('_');
    expect(tagToUrl(undefined)).toBe('_');
    expect(tagFromUrl('_')).toBe('');
  });

  test('a segment the router has already decoded is not decoded twice', () => {
    expect(tagFromUrl('_100% Kinderlieder')).toBe('100% Kinderlieder');
  });
});
