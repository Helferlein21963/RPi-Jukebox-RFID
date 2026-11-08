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

const newFolder = { folder: 'Max_uebernachtet', exists: false };

const existingFolder = {
  folder: 'Max_Hoerspiele',
  exists: true,
  numbered: false,
  artist: 'Ordner-Interpret',
  album: 'Ordner-Album',
  tracks: [{ file: 'Alt.mp3', title: 'Alt' }],
};

// The core: 'folders' are listed, 'folderInfo' is the answer for the folder name
const mockCore = ({ folderInfo = newFolder, start = { result: 'Max_uebernachtet' } } = {}) => {
  request.mockImplementation(async (command) => {
    if (command === 'ytimportListFolders') return { result: [{ folder: 'Max_Hoerspiele', tracks: 1 }] };
    if (command === 'ytimportFolderInfo') return { result: folderInfo };
    if (command === 'ytimportStart') return start;
    return { result: null };
  });
};

beforeEach(() => mockCore());

afterEach(() => jest.clearAllMocks());

const startButton = () => screen.getByRole('button', { name: /import\.editor\.start/ });

test('splits chapters by default and imports the edited tracks', async () => {
  render(<Editor info={info} />);

  expect(screen.getByDisplayValue('Teil 1')).toBeInTheDocument();
  expect(screen.getByDisplayValue('Teil 2')).toBeInTheDocument();
  await waitFor(() => expect(request).toHaveBeenCalledWith('ytimportFolderInfo', { name: 'Max übernachtet' }));
  expect(await screen.findByText('import.editor.folder-new {"folder":"Max_uebernachtet"}')).toBeInTheDocument();

  fireEvent.change(screen.getByDisplayValue('Teil 2'), { target: { value: 'Das Ende' } });
  // Second track up
  fireEvent.click(screen.getAllByRole('button', { name: 'import.editor.move-up' })[1]);
  fireEvent.click(startButton());

  await waitFor(() => expect(request).toHaveBeenCalledWith('ytimportStart', {
    folder: 'Max übernachtet',
    artist: 'Erzähler',
    album: 'Max übernachtet',
    cover: true,
    target: 'new',
    reorder: false,
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
  // Folder list and folder info loaded
  expect(await screen.findByText(/import\.editor\.folder-new/)).toBeInTheDocument();
});

test('reverses the order of the tracks', async () => {
  render(<Editor info={info} />);

  expect(await screen.findByText(/import\.editor\.folder-new/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'import.editor.reverse' }));
  fireEvent.click(startButton());

  await waitFor(() => expect(request).toHaveBeenCalledWith('ytimportStart', expect.objectContaining({
    tracks: [
      { url: 'https://www.youtube.com/watch?v=v', title: 'Teil 2', start: 100, end: 300 },
      { url: 'https://www.youtube.com/watch?v=v', title: 'Teil 1', start: 0, end: 100 },
    ],
  })));
});

test('adds to an existing folder, taking over its artist and album', async () => {
  mockCore({ folderInfo: existingFolder });
  render(<Editor info={info} targetFolder="Max_Hoerspiele" />);

  expect(await screen.findByText('import.editor.folder-existing-sorted {"count":1}')).toBeInTheDocument();
  expect(screen.getByDisplayValue('Ordner-Interpret')).toBeInTheDocument();
  expect(screen.getByDisplayValue('Ordner-Album')).toBeInTheDocument();
  // The files of the folder are only listed when the order is set
  expect(screen.queryByDisplayValue('Alt')).not.toBeInTheDocument();
  fireEvent.click(startButton());

  await waitFor(() => expect(request).toHaveBeenCalledWith('ytimportStart', expect.objectContaining({
    folder: 'Max_Hoerspiele',
    target: 'existing',
    reorder: false,
    artist: 'Ordner-Interpret',
    tracks: [
      { url: 'https://www.youtube.com/watch?v=v', title: 'Teil 1', start: 0, end: 100 },
      { url: 'https://www.youtube.com/watch?v=v', title: 'Teil 2', start: 100, end: 300 },
    ],
  })));
});

test('sets the order of the whole existing folder', async () => {
  mockCore({ folderInfo: existingFolder });
  render(<Editor info={info} targetFolder="Max_Hoerspiele" />);

  fireEvent.click(await screen.findByLabelText('import.editor.reorder'));
  // The file of the folder with its name, not as an editable title
  expect(screen.getByText('Alt.mp3')).toBeInTheDocument();
  expect(screen.queryByDisplayValue('Alt')).not.toBeInTheDocument();
  expect(screen.getByText('import.editor.reorder-hint')).toBeInTheDocument();
  // Every row shows its file name after the import
  expect(screen.getByText(/"name":"01 - Alt\.mp3"/)).toBeInTheDocument();
  expect(screen.getByText(/"name":"03 - Teil 2\.mp3"/)).toBeInTheDocument();
  // Only the new tracks count
  expect(startButton()).toHaveTextContent('{"count":2}');
  // The old file down, after the first new track
  fireEvent.click(screen.getAllByRole('button', { name: 'import.editor.move-down' })[0]);
  expect(screen.getByText(/"name":"02 - Alt\.mp3"/)).toBeInTheDocument();
  fireEvent.click(startButton());

  await waitFor(() => expect(request).toHaveBeenCalledWith('ytimportStart', expect.objectContaining({
    target: 'existing',
    reorder: true,
    tracks: [
      { url: 'https://www.youtube.com/watch?v=v', title: 'Teil 1', start: 0, end: 100 },
      { file: 'Alt.mp3' },
      { url: 'https://www.youtube.com/watch?v=v', title: 'Teil 2', start: 100, end: 300 },
    ],
  })));
});

test('lists the folders and offers a new one', async () => {
  render(<Editor info={info} />);
  await waitFor(() => expect(request).toHaveBeenCalledWith('ytimportListFolders'));

  const field = screen.getByRole('combobox', { name: 'import.editor.folder' });
  fireEvent.change(field, { target: { value: 'max' } });
  expect(await screen.findByText('Max_Hoerspiele')).toBeInTheDocument();
  expect(screen.getByText('import.editor.folder-create {"folder":"max"}')).toBeInTheDocument();

  fireEvent.click(screen.getByText('Max_Hoerspiele'));
  expect(field).toHaveValue('Max_Hoerspiele');
});

test('shows the error of the core', async () => {
  mockCore({ start: { error: 'Busy' } });
  render(<Editor info={info} />);
  expect(await screen.findByText(/import\.editor\.folder-new/)).toBeInTheDocument();

  fireEvent.click(startButton());
  expect(await screen.findByText('Busy')).toBeInTheDocument();
  expect(startButton()).toBeEnabled();
});
