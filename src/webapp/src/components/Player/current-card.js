import { useContext, useEffect, useState } from 'react';

import PubSubContext from '../../context/pubsub/context';
import request from '../../utils/request';
import { useCardsChanges } from '../../utils/use-updates';
import { cardMusic } from '../Cards/card-music';
import {
  isAlbumPlaying,
  isFolderPlaying,
  isSongPlaying,
  useMusicLibraryPath,
  useNowPlaying,
} from '../Library/now-playing';

const compareText = (a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' });

// How exactly the card's music matches the current song (higher is more specific), 0 if it doesn't
const matchScore = (music, nowPlaying) => {
  if (!music) return 0;
  if (music.song !== undefined) return isSongPlaying(nowPlaying, music.song) ? Number.MAX_SAFE_INTEGER : 0;
  if (music.album !== undefined) {
    return isAlbumPlaying(nowPlaying, music.albumartist, music.album) ? Number.MAX_SAFE_INTEGER - 1 : 0;
  }
  // Deeper folders first
  return isFolderPlaying(nowPlaying, music.folder) ? music.folder.length : 0;
};

/**
 * The card belonging to the current playback: { id, name }, or undefined.
 *
 * The card swiped last is taken if it plays the current song. Otherwise (playback started in the
 * web app, or the card was swiped long ago) a registered card that plays the current song:
 * the most specific one, cards with a name first.
 */
const findCurrentCard = ({ cardsList, swipedCardId, nowPlaying, libraryPath }) => {
  if (!nowPlaying?.isActive || !cardsList) return undefined;

  const score = (cardId) => matchScore(cardMusic(cardsList[cardId], libraryPath), nowPlaying);
  const toResult = (cardId) => ({ id: cardId, name: cardsList[cardId].name || undefined });

  if (swipedCardId && cardsList[swipedCardId] && score(swipedCardId) > 0) {
    return toResult(swipedCardId);
  }

  const [best] = Object.keys(cardsList)
    .map(cardId => ({ cardId, value: score(cardId), name: cardsList[cardId].name }))
    .filter(({ value }) => value > 0)
    .sort((a, b) => (
      (b.value - a.value)
      || ((a.name ? 0 : 1) - (b.name ? 0 : 1))
      || (a.name && b.name ? compareText(a.name, b.name) : 0)
      || compareText(a.cardId, b.cardId)
    ));

  return best ? toResult(best.cardId) : undefined;
};

/**
 * Card of the current playback among the given cards (see findCurrentCard), with isPlaying
 * (false while paused). undefined if none of the cards plays the current song.
 */
const useCurrentCardOf = (cardsList, libraryPath) => {
  const { state: { 'rfid.card_id': swipedCardId } } = useContext(PubSubContext);
  const nowPlaying = useNowPlaying();

  const card = findCurrentCard({ cardsList, swipedCardId, nowPlaying, libraryPath });
  return card && { ...card, isPlaying: nowPlaying.isPlaying };
};

/**
 * Card of the current playback, see useCurrentCardOf. The card list is loaded again
 * when another card is swiped, the song changes or the card database changed.
 */
const useCurrentCard = () => {
  const { state: { 'rfid.card_id': swipedCardId } } = useContext(PubSubContext);
  const { isActive, file } = useNowPlaying();
  const libraryPath = useMusicLibraryPath();
  const [cardsList, setCardsList] = useState(undefined);
  const cardsChanges = useCardsChanges();

  useEffect(() => {
    if (!isActive) return undefined;

    let isMounted = true;
    const loadCards = async () => {
      const { result, error } = await request('cardsList');
      if (!isMounted) return;
      if (result) setCardsList(result);
      if (error) console.error(error);
    };

    loadCards();
    return () => { isMounted = false; };
  }, [swipedCardId, isActive, file, cardsChanges]);

  return useCurrentCardOf(isActive ? cardsList : undefined, libraryPath);
};

export {
  findCurrentCard,
  useCurrentCard,
  useCurrentCardOf,
};
