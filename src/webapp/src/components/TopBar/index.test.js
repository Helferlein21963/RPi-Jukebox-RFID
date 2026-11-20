import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import PubSubContext from '../../context/pubsub/context';
import request from '../../utils/request';
import TopBar from './index';

// With a factory: an automatic mock would load the real module, which connects the sockets
jest.mock('../../utils/request', () => ({ __esModule: true, default: jest.fn() }));

jest.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key) => key, i18n: { language: 'de' } }),
}));

beforeEach(() => request.mockResolvedValue({ result: 30 }));
afterEach(() => jest.clearAllMocks());

const renderAt = (path) => render(
  <PubSubContext.Provider value={{ state: {} }}>
    <MemoryRouter initialEntries={[path]}>
      <TopBar />
    </MemoryRouter>
  </PubSubContext.Provider>
);

test('shows the volume slider and the clock on the other pages', async () => {
  renderAt('/library');

  expect(await screen.findByRole('slider')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'player.volume.mute' })).toBeInTheDocument();
  expect(document.querySelector('time')).toBeInTheDocument();
});

test('leaves the slider out on the start page, which has its own', () => {
  renderAt('/');

  expect(screen.queryByRole('slider')).not.toBeInTheDocument();
  expect(document.querySelector('time')).toBeInTheDocument();
});
