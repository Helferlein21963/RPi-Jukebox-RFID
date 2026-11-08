import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import request from '../../../utils/request';
import RenameDialog from './rename';

// With a factory: an automatic mock would load the real module, which connects the sockets
jest.mock('../../../utils/request', () => ({ __esModule: true, default: jest.fn() }));

// Translation keys with their values, e.g. 'library.rename.cards {"count":2}'
jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, values) => (values ? `${key} ${JSON.stringify(values)}` : key),
  }),
}));

const songInfo = {
  type: 'file',
  name: '01 Lied',
  extension: '.mp3',
  title: 'Lied',
  title_supported: true,
  cards: 2,
};

const PATH = '/music/Conni/01 Lied.mp3';

const mockCore = ({ info = songInfo, rename = { result: '/music/Conni/Intro.mp3' } } = {}) => {
  request.mockImplementation(async (command) => {
    if (command === 'getRenameInfo') return { result: info };
    if (command === 'renameLibraryEntry') return rename;
    return { result: null };
  });
};

const renderDialog = (props = {}) => {
  const onRenamed = jest.fn();
  render(<RenameDialog open path={PATH} onClose={jest.fn()} onRenamed={onRenamed} {...props} />);
  return onRenamed;
};

afterEach(() => jest.clearAllMocks());

test('renames a song and sets its title', async () => {
  mockCore();
  const onRenamed = renderDialog();

  const name = await screen.findByDisplayValue('01 Lied');
  expect(screen.getByText('.mp3')).toBeInTheDocument();
  expect(screen.getByText('library.rename.cards {"count":2}')).toBeInTheDocument();

  fireEvent.change(name, { target: { value: 'Intro' } });
  fireEvent.change(screen.getByDisplayValue('Lied'), { target: { value: 'Das Intro' } });
  fireEvent.click(screen.getByText('general.buttons.save'));

  await waitFor(() => expect(onRenamed).toHaveBeenCalledWith('/music/Conni/Intro.mp3'));
  expect(request).toHaveBeenCalledWith('getRenameInfo', { path: PATH });
  expect(request).toHaveBeenCalledWith('renameLibraryEntry', { path: PATH, new_name: 'Intro', title: 'Das Intro' });
});

test('an unchanged title is not sent', async () => {
  mockCore();
  renderDialog();

  fireEvent.change(await screen.findByDisplayValue('01 Lied'), { target: { value: 'Intro' } });
  fireEvent.click(screen.getByText('general.buttons.save'));

  await waitFor(() => expect(request).toHaveBeenCalledWith('renameLibraryEntry', { path: PATH, new_name: 'Intro' }));
});

test('save is disabled while nothing changed or the name is empty', async () => {
  mockCore();
  renderDialog();

  const name = await screen.findByDisplayValue('01 Lied');
  expect(screen.getByText('general.buttons.save').closest('button')).toBeDisabled();

  fireEvent.change(name, { target: { value: ' / ' } });
  expect(screen.getByText('general.buttons.save').closest('button')).toBeDisabled();
  expect(screen.getByText('library.rename.errors.invalid-name')).toBeInTheDocument();
});

test('shows the cleaned name', async () => {
  mockCore();
  renderDialog();

  fireEvent.change(await screen.findByDisplayValue('01 Lied'), { target: { value: 'AC/DC' } });

  expect(screen.getByText('library.rename.cleaned-name {"name":"AC DC"}')).toBeInTheDocument();
});

test('a folder has no title field', async () => {
  mockCore({ info: { type: 'directory', name: 'Conni', extension: '', title: '', title_supported: false, cards: 0 } });
  renderDialog({ path: '/music/Conni' });

  await screen.findByDisplayValue('Conni');
  expect(screen.getByText('library.rename.title-folder')).toBeInTheDocument();
  expect(screen.queryAllByText('library.rename.song-title')).toHaveLength(0);
  expect(screen.queryByText(/library\.rename\.cards/)).not.toBeInTheDocument();
});

test('the title field is disabled without mutagen', async () => {
  mockCore({ info: { ...songInfo, title_supported: false } });
  renderDialog();

  expect(await screen.findByDisplayValue('Lied')).toBeDisabled();
  expect(screen.getByText('library.rename.title-not-supported')).toBeInTheDocument();
});

test('shows the error of the core', async () => {
  mockCore({ rename: { error: "ValueError: 'Conni' is being played. Stop the playback first." } });
  const onRenamed = renderDialog();

  fireEvent.change(await screen.findByDisplayValue('01 Lied'), { target: { value: 'Intro' } });
  fireEvent.click(screen.getByText('general.buttons.save'));

  expect(await screen.findByText('library.rename.errors.playing')).toBeInTheDocument();
  expect(onRenamed).not.toHaveBeenCalled();
});
