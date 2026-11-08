// Helpers for the custom timer time (values of <input type="time">: 'HH:MM' or 'HH:MM:SS')

// 'HH:MM' -> { hours, minutes }, or null if invalid
const parseTime = (value) => {
  const match = /^(\d{1,2}):(\d{2})/.exec(value || '');
  if (!match) return null;
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (hours > 23 || minutes > 59) return null;
  return { hours, minutes };
};

// Duration 'HH:MM' -> seconds (0 if invalid)
const durationSeconds = (value) => {
  const time = parseTime(value);
  return time ? (time.hours * 60 + time.minutes) * 60 : 0;
};

// Seconds from now until the next time the clock shows 'HH:MM' (today or tomorrow), 0 if invalid
const secondsUntil = (value, now = new Date()) => {
  const time = parseTime(value);
  if (!time) return 0;
  const target = new Date(now);
  target.setHours(time.hours, time.minutes, 0, 0);
  if (target <= now) target.setDate(target.getDate() + 1);
  return Math.round((target - now) / 1000);
};

// Date -> 'HH:MM'
const toTimeValue = (date) => (
  [date.getHours(), date.getMinutes()].map((n) => String(n).padStart(2, '0')).join(':')
);

// Default end time: in an hour, rounded up to 5 minutes
const defaultClock = (now = new Date()) => {
  const date = new Date(now.getTime() + 60 * 60 * 1000);
  date.setMinutes(Math.ceil(date.getMinutes() / 5) * 5, 0, 0);
  return toTimeValue(date);
};

export {
  defaultClock,
  durationSeconds,
  parseTime,
  secondsUntil,
  toTimeValue,
};
