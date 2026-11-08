import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import request from '../../utils/request';
import Editor from './editor';

// With a factory: an automatic mock would load the real module, which connects the sockets
jest.mock('../../utils/request', () => ({ __esModule: true, default: jest.fn() }));

// Translation keys with their values, e.g. 'import.editor.start {"count":2}'
jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, values) => (values ? `${key} ${JSON.stringify(values)}` : key),
  }),
}));

const info = {
  kind: 'video',
  url: 'https://youtu.be/v',
  title: 'Max übernachtet',
  uploader: 'Erzähler',
  thumbnail: null,
  folder: 'Max_uebernachtet',
  truncated: false,
  entries: [{
    url: 'https://www.youtube.com/watch?v=v',
    title: 'Max übernachtet',
    duration: 300,
    available: true,
    chapters: [
      { title: 'Teil 1', start: 0, end: 100 },
      { title: 'Teil 2', start: 100, end: 300 },
    ],
  }],
};

beforeEach(() => {
  request.mockImplementation(async (command) => {
    if (command === 'ytimportCheckFolder') return { result: { folder: 'Max_uebernachtet', exists: false } };
    if (command === 'ytimportStart') return { result: 'Max_uebernachtet' };
    return { result: null };
  });
});

afterEach(() => jest.clearAllMocks());

const startButton = () => screen.getByRole('button', { name: /import\.editor\.start/ });

test('splits chapters by default and imports the edited tracks', async () => {
  render(<Editor info={info} />);

  expect(screen.getByDisplayValue('Teil 1')).toBeInTheDocument();
  expect(screen.getByDisplayValue('Teil 2')).toBeInTheDocument();
  await waitFor(() => expect(request).toHaveBeenCalledWith('ytimportCheckFolder', { name: 'Max übernachtet' }));

  fireEvent.change(screen.getByDisplayValue('Teil 2'), { target: { value: 'Das Ende' } });
  // Second track up
  fireEvent.click(screen.getAllByRole('button', { name: 'import.editor.move-up' })[1]);
  fireEvent.click(startButton());

  await waitFor(() => expect(request).toHaveBeenCalledWith('ytimportStart', {
    folder: 'Max übernachtet',
    artist: 'Erzähler',
    album: 'Max übernachtet',
    cover: true,
    tracks: [
      { url: 'https://www.youtube.com/watch?v=v', title: 'Das Ende', start: 100, end: 300 },
      { url: 'https://www.youtube.com/watch?v=v', title: 'Teil 1', start: 0, end: 100 },
    ],
  }));
});

test('the whole video as one track, deselected tracks are not imported', async () => {
  render(<Editor info={info} />);

  fireEvent.click(screen.getByLabelText(/import\.editor\.split-chapters/));
  expect(screen.queryByDisplayValue('Teil 1')).not.toBeInTheDocument();
  expect(startButton()).toHaveTextContent('{"count":1}');

  fireEvent.click(screen.getByRole('checkbox', { name: 'Max übernachtet' }));
  expect(startButton()).toBeDisabled();
});

test('reverses the order of the tracks', async () => {
  render(<Editor info={info} />);

  fireEvent.click(screen.getByRole('button', { name: 'import.editor.reverse' }));
  fireEvent.click(startButton());

  await waitFor(() => expect(request).toHaveBeenCalledWith('ytimportStart', expect.objectContaining({
    tracks: [
      { url: 'https://www.youtube.com/watch?v=v', title: 'Teil 2', start: 100, end: 300 },
      { url: 'https://www.youtube.com/watch?v=v', title: 'Teil 1', start: 0, end: 100 },
    ],
  })));
});

test('an existing folder blocks the import', async () => {
  request.mockImplementation(async (command) => (
    command === 'ytimportCheckFolder'
      ? { result: { folder: 'Max_uebernachtet', exists: true } }
      : { result: null }
  ));
  render(<Editor info={info} />);

  expect(await screen.findByText(/import\.editor\.folder-exists/)).toBeInTheDocument();
  expect(startButton()).toBeDisabled();
});

test('shows the error of the core', async () => {
  request.mockImplementation(async (command) => (
    command === 'ytimportStart'
      ? { error: 'Busy' }
      : { result: { folder: 'Max_uebernachtet', exists: false } }
  ));
  render(<Editor info={info} />);

  fireEvent.click(startButton());
  expect(await screen.findByText('Busy')).toBeInTheDocument();
  expect(startButton()).toBeEnabled();
});
