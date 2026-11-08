import React from 'react';
import { act, render, screen } from '@testing-library/react';

import Clock from './index';

jest.mock('react-i18next', () => ({
  useTranslation: () => ({ i18n: { language: 'de' } }),
}));

afterEach(() => jest.useRealTimers());

test('shows the current date and time and follows the clock', () => {
  jest.useFakeTimers('modern');
  jest.setSystemTime(new Date(2026, 10, 8, 18, 11, 58));
  render(<Clock />);

  expect(screen.getByText('18:11')).toBeInTheDocument();
  expect(screen.getByText(/8\. Nov/)).toBeInTheDocument();

  act(() => {
    jest.advanceTimersByTime(3000);
  });
  expect(screen.getByText('18:12')).toBeInTheDocument();
});
