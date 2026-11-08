import { defaultClock, durationSeconds, parseTime, secondsUntil, toTimeValue } from './utils';

describe('parseTime', () => {
  it('reads HH:MM and HH:MM:SS', () => {
    expect(parseTime('01:30')).toEqual({ hours: 1, minutes: 30 });
    expect(parseTime('23:59:00')).toEqual({ hours: 23, minutes: 59 });
    expect(parseTime('7:05')).toEqual({ hours: 7, minutes: 5 });
  });

  it('rejects invalid values', () => {
    expect(parseTime('')).toBeNull();
    expect(parseTime(undefined)).toBeNull();
    expect(parseTime('24:00')).toBeNull();
    expect(parseTime('12:60')).toBeNull();
    expect(parseTime('abc')).toBeNull();
  });
});

test('durationSeconds', () => {
  expect(durationSeconds('01:30')).toBe(5400);
  expect(durationSeconds('00:05')).toBe(300);
  expect(durationSeconds('00:00')).toBe(0);
  expect(durationSeconds('')).toBe(0);
});

describe('secondsUntil', () => {
  const now = new Date(2026, 10, 8, 19, 15, 30);

  it('counts until the time today', () => {
    expect(secondsUntil('20:00', now)).toBe(44 * 60 + 30);
  });

  it('takes tomorrow for a time that has passed', () => {
    expect(secondsUntil('07:00', now)).toBe((11 * 60 + 44) * 60 + 30);
    expect(secondsUntil('19:15', now)).toBe(24 * 3600 - 30);
  });

  it('returns 0 for invalid values', () => {
    expect(secondsUntil('', now)).toBe(0);
  });
});

test('toTimeValue and defaultClock', () => {
  expect(toTimeValue(new Date(2026, 0, 1, 7, 5))).toBe('07:05');
  expect(defaultClock(new Date(2026, 0, 1, 19, 12))).toBe('20:15');
  expect(defaultClock(new Date(2026, 0, 1, 19, 15))).toBe('20:15');
  expect(defaultClock(new Date(2026, 0, 1, 23, 58))).toBe('01:00');
});
