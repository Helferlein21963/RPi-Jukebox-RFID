import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createTheme, ThemeProvider } from '@mui/material/styles';

import PubSubContext from '../../../context/pubsub/context';
import request from '../../../utils/request';
import SettingsTimers from './index';
import { secondsUntil, toTimeValue } from './utils';

jest.mock('../../../utils/request', () => jest.fn());

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, params) => (params ? `${key} ${JSON.stringify(params)}` : key),
    i18n: { language: 'de' },
  }),
}));

// The Pi is slow
jest.setTimeout(30000);

const DISABLED = { enabled: false, remaining_seconds: 0, wait_seconds: 3600 };

// Core mock: timer states by plugin name, every call recorded
let pending = 0;
const mockCore = (states = {}) => {
  request.mockImplementation(async (command) => {
    pending += 1;
    await Promise.resolve();
    pending -= 1;
    const [plugin, method] = command.split('.');
    if (method === 'get_state') {
      return { result: { ...DISABLED, fade_seconds: 300, ...states[plugin] } };
    }
    return { result: null };
  });
};

// Wait for all requests and the state updates after them (else they run after the test environment is gone)
const settle = async () => {
  await waitFor(() => expect(pending).toBe(0));
  await waitFor(() => screen.getAllByRole('button').forEach((button) => expect(button).toBeEnabled()));
};

// No ripple animation: its timeouts would fire after the test environment is gone
const theme = createTheme({ components: { MuiButtonBase: { defaultProps: { disableRipple: true } } } });

const Timers = ({ pubsubState }) => (
  <ThemeProvider theme={theme}>
    <PubSubContext.Provider value={{ state: pubsubState, setState: () => {} }}>
      <SettingsTimers />
    </PubSubContext.Provider>
  </ThemeProvider>
);

const renderTimers = (pubsubState = {}) => render(<Timers pubsubState={pubsubState} />);

beforeEach(() => {
  localStorage.clear();
  request.mockReset();
  pending = 0;
});

test('shows that no timer is active', async () => {
  mockCore();
  renderTimers();

  expect(await screen.findByText('settings.timers.none-active')).toBeInTheDocument();
  expect(request).toHaveBeenCalledWith('timer_shutdown.get_state');
  expect(request).toHaveBeenCalledWith('timer_stop_player.get_state');
  expect(request).toHaveBeenCalledWith('timer_fade_volume.get_state');
});

test('starts the chosen timer only with the start button', async () => {
  mockCore();
  renderTimers();
  await screen.findByText('settings.timers.none-active');

  fireEvent.click(screen.getByRole('button', { name: /settings.timers.short-stop-player/ }));
  fireEvent.click(screen.getByRole('button', { name: /"value":10}/ }));
  expect(request).not.toHaveBeenCalledWith('timer_stop_player', expect.anything());

  fireEvent.click(screen.getByRole('button', { name: /settings.timers.start/ }));
  await waitFor(() => expect(request).toHaveBeenCalledWith('timer_stop_player', { wait_seconds: 600 }));
  expect(request).not.toHaveBeenCalledWith('timer_stop_player.cancel');
  expect(localStorage.getItem('timerLastType')).toBe('stop-player');
  expect(localStorage.getItem('timerLastMinutes')).toBe('10');
  await settle();
});

test('shows a running timer with countdown, cancels it', async () => {
  mockCore({ timer_shutdown: { enabled: true, remaining_seconds: 125, wait_seconds: 600 } });
  renderTimers();

  expect(await screen.findByText('2:05')).toBeInTheDocument();
  expect(screen.getByText('settings.timers.shutdown')).toBeInTheDocument();
  expect(screen.queryByText('settings.timers.none-active')).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: 'settings.timers.cancel' }));
  await waitFor(() => expect(request).toHaveBeenCalledWith('timer_shutdown.cancel'));
  await settle();
});

test('restarts a running timer of the same type', async () => {
  localStorage.setItem('timerLastType', 'shutdown');
  localStorage.setItem('timerLastMinutes', '5');
  mockCore({ timer_shutdown: { enabled: true, remaining_seconds: 125, wait_seconds: 600 } });
  renderTimers();
  await screen.findByText('2:05');

  fireEvent.click(screen.getByRole('button', { name: /settings.timers.restart/ }));
  await waitFor(() => expect(request).toHaveBeenCalledWith('timer_shutdown', { wait_seconds: 300 }));
  const calls = request.mock.calls.map(([command]) => command);
  expect(calls.indexOf('timer_shutdown.cancel')).toBeLessThan(calls.lastIndexOf('timer_shutdown'));
  await settle();
});

test('follows published timer states', async () => {
  mockCore();
  const { rerender } = renderTimers();
  await screen.findByText('settings.timers.none-active');
  await settle();

  const published = { 'timers.timer_fade_volume': { enabled: true, remaining_seconds: 60, wait_seconds: 60 } };
  rerender(<Timers pubsubState={published} />);
  expect(await screen.findByText('1:00')).toBeInTheDocument();
  expect(screen.getByText('settings.timers.fade-volume')).toBeInTheDocument();
});

test('starts a timer with a custom duration', async () => {
  mockCore();
  renderTimers();
  await screen.findByText('settings.timers.none-active');

  fireEvent.click(screen.getByRole('button', { name: /settings.timers.custom$/ }));
  const input = screen.getByLabelText('settings.timers.custom-duration-label');
  expect(input).toHaveAttribute('type', 'time');

  fireEvent.change(input, { target: { value: '00:00' } });
  expect(screen.getByText('settings.timers.custom-invalid')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /settings.timers.start/ })).toBeDisabled();

  fireEvent.change(input, { target: { value: '01:30' } });
  const startButton = screen.getByRole('button', { name: /settings.timers.start/ });
  expect(startButton).toHaveTextContent('1:30');
  fireEvent.click(startButton);
  await waitFor(() => expect(request).toHaveBeenCalledWith(
    'timer_fade_volume', { wait_seconds: 5400, fade_seconds: 10 }
  ));
  expect(localStorage.getItem('timerLastMinutes')).toBe('custom');
  expect(localStorage.getItem('timerCustomDuration')).toBe('01:30');
  await settle();
});

test('starts a timer that ends at a time of day', async () => {
  mockCore();
  renderTimers();
  await screen.findByText('settings.timers.none-active');

  fireEvent.click(screen.getByRole('button', { name: /settings.timers.custom$/ }));
  fireEvent.click(screen.getByRole('button', { name: 'settings.timers.custom-clock' }));
  const input = screen.getByLabelText('settings.timers.custom-clock-label');

  // Two minutes from now (tomorrow if that is after midnight: still within a day)
  const end = new Date(Date.now() + 2 * 60 * 1000);
  const value = toTimeValue(end);
  fireEvent.change(input, { target: { value } });
  const startButton = screen.getByRole('button', { name: /settings.timers.start/ });
  expect(startButton).toHaveTextContent('settings.timers.until');
  expect(startButton).toHaveTextContent(value);

  fireEvent.click(startButton);
  const expected = secondsUntil(value);
  await waitFor(() => expect(request).toHaveBeenCalledWith('timer_fade_volume', expect.anything()));
  const [, { wait_seconds }] = request.mock.calls.find(([command]) => command === 'timer_fade_volume');
  expect(Math.abs(wait_seconds - expected)).toBeLessThanOrEqual(2);
  expect(wait_seconds).toBeGreaterThan(0);
  expect(localStorage.getItem('timerCustomMode')).toBe('clock');
  expect(screen.getByText(/settings.timers.now/)).toBeInTheDocument();
  await settle();
});

test('fade out timer: seconds field with default 10, only for this type', async () => {
  mockCore();
  renderTimers();
  await screen.findByText('settings.timers.none-active');

  const field = screen.getByLabelText('settings.timers.fade-seconds-label');
  expect(field).toHaveValue(10);
  expect(screen.getByText(/settings.timers.hint-fade-volume/)).toHaveTextContent('duration-seconds {\\"value\\":10}');

  fireEvent.change(field, { target: { value: '0' } });
  expect(screen.getByText('settings.timers.fade-seconds-invalid')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /settings.timers.start/ })).toBeDisabled();

  fireEvent.change(field, { target: { value: '45' } });
  fireEvent.click(screen.getByRole('button', { name: /"value":5}/ }));
  fireEvent.click(screen.getByRole('button', { name: /settings.timers.start/ }));
  await waitFor(() => expect(request).toHaveBeenCalledWith(
    'timer_fade_volume', { wait_seconds: 300, fade_seconds: 45 }
  ));
  expect(localStorage.getItem('timerFadeSeconds')).toBe('45');
  await settle();

  // Not for the other timers
  fireEvent.click(screen.getByRole('button', { name: /settings.timers.short-shutdown/ }));
  expect(screen.queryByLabelText('settings.timers.fade-seconds-label')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /settings.timers.start/ }));
  await waitFor(() => expect(request).toHaveBeenCalledWith('timer_shutdown', { wait_seconds: 300 }));
  await settle();
});

test('preset durations show their end time', async () => {
  mockCore();
  renderTimers();
  await screen.findByText('settings.timers.none-active');

  const end = new Date(Date.now() + 30 * 60 * 1000)
    .toLocaleTimeString('de', { hour: '2-digit', minute: '2-digit' });
  const chip = screen.getByRole('button', { name: /"value":30}/ });
  expect(chip).toHaveTextContent(`settings.timers.chip-until {"time":"${end}"}`);
});
