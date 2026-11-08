import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom';

import Library from './index';

// The lists load from the core: only the header and the view are of interest here
jest.mock('./lists', () => {
  const { useParams } = jest.requireActual('react-router-dom');
  const LibraryHeader = jest.requireActual('./library-header').default;
  return {
    __esModule: true,
    default: () => {
      const { '*': view } = useParams();
      return (
        <>
          <LibraryHeader musicFilter="" setMusicFilter={() => {}} sorts={{}} onSortChange={() => {}} />
          <div data-testid="view">{view}</div>
        </>
      );
    },
  };
});

jest.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key) => key }),
}));

const renderApp = () => render(
  <MemoryRouter initialEntries={['/library']}>
    <Link to="/">start</Link>
    <Link to="/library">library</Link>
    <Routes>
      <Route index element={<div>start page</div>} />
      <Route path="library/*" element={<Library />} />
    </Routes>
  </MemoryRouter>
);

beforeEach(() => localStorage.clear());

test('opens with the folders, their button comes first', () => {
  renderApp();

  expect(screen.getByTestId('view')).toHaveTextContent('folders');
  const buttons = screen.getAllByRole('button').filter((button) => button.value);
  expect(buttons.map((button) => button.value)).toEqual(['folders', 'albums', 'songs']);
});

test('opens again with the view chosen last', () => {
  renderApp();

  fireEvent.click(screen.getByRole('button', { name: 'library.header.songs' }));
  expect(screen.getByTestId('view')).toHaveTextContent('songs');

  fireEvent.click(screen.getByText('start'));
  expect(screen.getByText('start page')).toBeInTheDocument();
  fireEvent.click(screen.getByText('library'));
  expect(screen.getByTestId('view')).toHaveTextContent('songs');
});

test('offers the sorts of the view', () => {
  renderApp();

  fireEvent.click(screen.getByRole('button', { name: 'library.header.sort-label' }));
  expect(screen.getByText('library.header.sort.recent')).toBeInTheDocument();
  expect(screen.queryByText('library.header.sort.artist')).not.toBeInTheDocument();
});
