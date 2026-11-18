import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import {
  Box,
  Chip,
} from '@mui/material';

import BookmarkIcon from '@mui/icons-material/Bookmark';

import request from '../../utils/request';
import { useCardsChanges } from '../../utils/use-updates';
import { cardMusic, toRelativePath } from '../Cards/card-music';

// The same (empty) list for everything without a card, so memoized list items don't re-render
const NO_CARDS = Object.freeze([]);

const compareText = (a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' });

const albumKey = (albumartist, album) => JSON.stringify([albumartist || '', album || '']);

// Cards with a name first, alphabetically, then the others by ID
const compareCards = (a, b) => (
  ((a.name ? 0 : 1) - (b.name ? 0 : 1))
  || (a.name && b.name ? compareText(a.name, b.name) : 0)
  || compareText(a.id, b.id)
);

/**
 * The registered cards by the music they play: { folders, songs, albums }, each mapping
 * the folder / song (relative to the library) or album key to a list of { id, name }.
 * Cards that don't start music (volume, toggle, ...) aren't in it.
 */
const buildCardIndex = (cardsList, libraryPath) => {
  const index = { folders: {}, songs: {}, albums: {} };

  Object.entries(cardsList || {}).forEach(([id, card]) => {
    const music = cardMusic(card, libraryPath);
    if (!music) return;

    const [map, key] = (
      music.song !== undefined ? [index.songs, music.song]
        : music.album !== undefined ? [index.albums, albumKey(music.albumartist, music.album)]
          : [index.folders, music.folder]
    );
    (map[key] = map[key] || []).push({ id, name: card.name || undefined });
  });

  Object.values(index).forEach(map => Object.values(map).forEach(cards => cards.sort(compareCards)));
  return index;
};

const LibraryCardsContext = createContext({ index: undefined, libraryPath: undefined });

/**
 * Loads the card list once for all views of the library (again when the card database changed).
 * Nothing is matched until the library path is known: card folders can be absolute.
 */
const LibraryCardsProvider = ({ libraryPath, children }) => {
  const [cardsList, setCardsList] = useState(undefined);
  const cardsChanges = useCardsChanges();

  useEffect(() => {
    let isMounted = true;
    const loadCards = async () => {
      const { result, error } = await request('cardsList');
      if (!isMounted) return;
      if (result) setCardsList(result);
      if (error) console.error(error);
    };

    loadCards();
    return () => { isMounted = false; };
  }, [cardsChanges]);

  const value = useMemo(() => ({
    index: cardsList && libraryPath ? buildCardIndex(cardsList, libraryPath) : undefined,
    libraryPath,
  }), [cardsList, libraryPath]);

  return <LibraryCardsContext.Provider value={value}>{children}</LibraryCardsContext.Provider>;
};

/** Cards playing this folder (absolute or relative path) */
const useFolderCards = (folder) => {
  const { index, libraryPath } = useContext(LibraryCardsContext);
  if (!index || !folder) return NO_CARDS;
  return index.folders[toRelativePath(folder, libraryPath)] || NO_CARDS;
};

/** Cards playing this single song (absolute or relative path) */
const useSongCards = (file) => {
  const { index, libraryPath } = useContext(LibraryCardsContext);
  if (!index || !file) return NO_CARDS;
  return index.songs[toRelativePath(file, libraryPath)] || NO_CARDS;
};

/** Cards playing this album */
const useAlbumCards = (albumartist, album) => {
  const { index } = useContext(LibraryCardsContext);
  if (!index || !album) return NO_CARDS;
  return index.albums[albumKey(albumartist, album)] || NO_CARDS;
};

const cardLabel = ({ id, name }) => name || id;

/** The cards as a line of text with the card icon, for list items. Nothing without cards. */
const CardNames = ({ cards }) => {
  const { t } = useTranslation();
  if (!cards.length) return null;

  return (
    <Box
      component="span"
      title={t('library.cards.assigned', { count: cards.length })}
      sx={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'primary.main' }}
    >
      <BookmarkIcon sx={{ fontSize: '1em' }} aria-label={t('library.cards.assigned', { count: cards.length })} />
      <Box component="span" sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {cards.map(cardLabel).join(', ')}
      </Box>
    </Box>
  );
};

/** The cards as chips that open the card, for the header of a folder or album. Nothing without cards. */
const CardChips = ({ cards, sx }) => {
  const { t } = useTranslation();
  if (!cards.length) return null;

  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: '8px', ...sx }}>
      {cards.map(card => (
        <Chip
          key={card.id}
          icon={<BookmarkIcon />}
          label={cardLabel(card)}
          title={t('library.cards.edit-card')}
          component={Link}
          to={`/cards/${encodeURIComponent(card.id)}/edit`}
          clickable
          size="small"
          color="primary"
          variant="outlined"
        />
      ))}
    </Box>
  );
};

/** Secondary text of a list item with the cards below it */
const withCards = (secondary, cards) => (
  cards.length
    ? <>
        {secondary && <Box component="span" sx={{ display: 'block' }}>{secondary}</Box>}
        <CardNames cards={cards} />
      </>
    : secondary
);

export {
  buildCardIndex,
  CardChips,
  CardNames,
  LibraryCardsProvider,
  useAlbumCards,
  useFolderCards,
  useSongCards,
  withCards,
};
