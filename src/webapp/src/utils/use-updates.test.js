import React from 'react';
import { render, screen } from '@testing-library/react';

import PubSubContext from '../context/pubsub/context';
import { useCardsChanges, useLibraryChanges } from './use-updates';

const Changes = () => (
  <>
    <span data-testid="library">{useLibraryChanges()}</span>
    <span data-testid="cards">{useCardsChanges()}</span>
  </>
);

const withState = (state) => (
  <PubSubContext.Provider value={{ state }}>
    <Changes />
  </PubSubContext.Provider>
);

const counts = () => [screen.getByTestId('library').textContent, screen.getByTestId('cards').textContent];

test('counts only changes of the published versions', () => {
  // Not published yet
  const { rerender } = render(withState({}));
  expect(counts()).toEqual(['0', '0']);

  // First versions: the lists were just loaded
  rerender(withState({ 'library.updated': { db_update: 100 }, 'cards.database.has_changed': 1.5 }));
  expect(counts()).toEqual(['0', '0']);

  // The core resends the same versions to new subscribers (new objects, same values)
  rerender(withState({ 'library.updated': { db_update: 100 }, 'cards.database.has_changed': 1.5 }));
  expect(counts()).toEqual(['0', '0']);

  rerender(withState({ 'library.updated': { db_update: 200 }, 'cards.database.has_changed': 1.5 }));
  expect(counts()).toEqual(['1', '0']);

  rerender(withState({ 'library.updated': { db_update: 200 }, 'cards.database.has_changed': 2.5 }));
  expect(counts()).toEqual(['1', '1']);
});
