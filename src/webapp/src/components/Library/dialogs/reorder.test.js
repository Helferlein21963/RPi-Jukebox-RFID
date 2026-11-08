import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';

import request from '../../../utils/request';
import ReorderDialog from './reorder';
import { reorderNames } from './utils';
import { dropIndex } from '../../../utils/use-drag-sort';

// jsdom has no pointer events: without clientY and pointerId, dragging can't be tested
if (!window.PointerEvent) {
  window.PointerEvent = class PointerEvent extends MouseEvent {
    constructor(type, params = {}) {
      super(type, params);
      this.pointerId = params.pointerId;
      this.pointerType = params.pointerType;
    }
  };
}

// With a factory: an automatic mock would load the real module, which connects the sockets
jest.mock('../../../utils/request', () => ({ __esModule: true, default: jest.fn() }));

// Translation keys with their values, e.g. 'library.reorder.becomes {"name":"01 - A.mp3"}'
jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, values) => (values ? `${key} ${JSON.stringify(values)}` : key),
  }),
}));

const FOLDER = '/music/Maus';

const songs = [
  { file: '01 - Aufsteigen.mp3', title: 'Aufsteigen', track: 1, modified: 100 },
  { file: 'Hocke.mp3', title: 'In der Hocke', track: null, modified: 300 },
  { file: 'Brücke.ogg', title: '', track: 3, modified: 200 },
];

const mockCore = ({ info = { result: songs }, reorder = { result: [] } } = {}) => {
  request.mockImplementation(async (command) => {
    if (command === 'getOrderInfo') return info;
    if (command === 'reorderFolder') return reorder;
    return { result: null };
  });
};

const renderDialog = () => {
  const onSaved = jest.fn();
  render(<ReorderDialog open folder={FOLDER} onClose={jest.fn()} onSaved={onSaved} />);
  return onSaved;
};

const shownFiles = () => screen.getAllByRole('listitem').map((item) => (
  within(item).getAllByText(/\.(mp3|ogg)$/)[0].textContent
));

afterEach(() => jest.clearAllMocks());

test('the new names, like the core makes them', () => {
  expect(reorderNames(['Zebra.mp3', '07 - Alt.ogg', '1_x?.mp3'])).toEqual([
    '01 - Zebra.mp3', '02 - Alt.ogg', '03 - x.mp3']);
  expect(reorderNames(Array(100).fill('a.mp3'))[0]).toBe('001 - a.mp3');
});

test('sorts, moves and saves the order', async () => {
  mockCore();
  const onSaved = renderDialog();

  expect(await screen.findByText('Hocke.mp3')).toBeInTheDocument();
  expect(request).toHaveBeenCalledWith('getOrderInfo', { folder: FOLDER });
  expect(screen.getByText('library.reorder.unchanged')).toBeInTheDocument();
  expect(screen.getByText('library.reorder.becomes {"name":"02 - Hocke.mp3"}')).toBeInTheDocument();

  fireEvent.click(screen.getByText('library.reorder.sort.newest'));
  expect(shownFiles()).toEqual(['Hocke.mp3', 'Brücke.ogg', '01 - Aufsteigen.mp3']);
  fireEvent.click(screen.getByText('library.reorder.sort.track'));
  expect(shownFiles()).toEqual(['01 - Aufsteigen.mp3', 'Brücke.ogg', 'Hocke.mp3']);
  fireEvent.click(screen.getByText('library.reorder.sort.name-desc'));
  expect(shownFiles()).toEqual(['Hocke.mp3', 'Brücke.ogg', '01 - Aufsteigen.mp3']);
  fireEvent.click(screen.getByText('library.reorder.sort.name-asc'));
  expect(shownFiles()).toEqual(['01 - Aufsteigen.mp3', 'Brücke.ogg', 'Hocke.mp3']);

  // Last one up
  fireEvent.click(screen.getAllByRole('button', { name: 'library.reorder.move-up' })[2]);
  expect(shownFiles()).toEqual(['01 - Aufsteigen.mp3', 'Hocke.mp3', 'Brücke.ogg']);
  fireEvent.click(screen.getByText('general.buttons.save'));

  await waitFor(() => expect(onSaved).toHaveBeenCalled());
  expect(request).toHaveBeenCalledWith('reorderFolder', {
    folder: FOLDER,
    files: ['01 - Aufsteigen.mp3', 'Hocke.mp3', 'Brücke.ogg'],
  });
});

test('nothing to save when the names fit already', async () => {
  mockCore({ info: { result: [songs[0], { ...songs[1], file: '02 - Hocke.mp3' }] } });
  renderDialog();

  expect(await screen.findByText('02 - Hocke.mp3')).toBeInTheDocument();
  expect(screen.getByText('general.buttons.save')).toBeDisabled();
});

test('shows why the order can not be changed', async () => {
  mockCore({ reorder: { error: "ValueError: 'Maus' is being played. Stop the playback first." } });
  const onSaved = renderDialog();

  fireEvent.click(await screen.findByText('library.reorder.sort.newest'));
  fireEvent.click(screen.getByText('general.buttons.save'));

  expect(await screen.findByText('library.rename.errors.playing')).toBeInTheDocument();
  expect(onSaved).not.toHaveBeenCalled();
});

test('a folder with a playlist file', async () => {
  mockCore({ info: { error: "ValueError: The order of 'Maus' is set by a playlist or stream file" } });
  renderDialog();

  expect(await screen.findByText('library.reorder.errors.special')).toBeInTheDocument();
  expect(screen.getByText('general.buttons.save')).toBeDisabled();
});

test('where a dragged row lands', () => {
  expect(dropIndex([75, 125], 10)).toBe(0);
  expect(dropIndex([75, 125], 100)).toBe(1);
  expect(dropIndex([75, 125], 130)).toBe(2);
  expect(dropIndex([], 130)).toBe(0);
});

test('drags a song to another place', async () => {
  mockCore();
  renderDialog();
  expect(await screen.findByText('Hocke.mp3')).toBeInTheDocument();

  // A high scroll area (no scrolling at its edges) with rows of 50 px, one below the other
  document.querySelector('.MuiDialogContent-root').getBoundingClientRect = () => ({ top: 0, bottom: 1000 });
  screen.getAllByRole('listitem').forEach((row, idx) => {
    row.getBoundingClientRect = () => ({ top: idx * 50, bottom: idx * 50 + 50, height: 50 });
  });

  // The first song below the last one
  const handle = screen.getAllByTitle('library.reorder.drag')[0];
  fireEvent.pointerDown(handle, { pointerId: 1, pointerType: 'touch', clientY: 25 });
  fireEvent.pointerMove(window, { pointerId: 1, pointerType: 'touch', clientY: 130 });
  // The dragged song follows the finger, the others make room; the list changes when it is dropped
  await waitFor(() => expect(screen.getAllByRole('listitem')[0]).toHaveStyle('transform: translateY(105px)'));
  expect(screen.getAllByRole('listitem')[1]).toHaveStyle('transform: translateY(-50px)');
  expect(screen.getAllByRole('listitem')[2]).toHaveStyle('transform: translateY(-50px)');
  expect(shownFiles()).toEqual(['01 - Aufsteigen.mp3', 'Hocke.mp3', 'Brücke.ogg']);

  act(() => {
    fireEvent.pointerUp(window, { pointerId: 1, pointerType: 'touch', clientY: 130 });
  });
  expect(shownFiles()).toEqual(['Hocke.mp3', 'Brücke.ogg', '01 - Aufsteigen.mp3']);
  expect(screen.getAllByRole('listitem')[2].style.transform).toBe('');

  fireEvent.click(screen.getByText('general.buttons.save'));
  await waitFor(() => expect(request).toHaveBeenCalledWith('reorderFolder', {
    folder: FOLDER,
    files: ['Hocke.mp3', 'Brücke.ogg', '01 - Aufsteigen.mp3'],
  }));
});
