import { useContext, useEffect, useRef, useState } from 'react';

import PubSubContext from '../context/pubsub/context';

// Topics the core publishes after changes, see config.js SUBSCRIPTIONS
const LIBRARY_TOPIC = 'library.updated';
const CARDS_TOPIC = 'cards.database.has_changed';

/**
 * Version of the music library: the time stamp of the MPD database, undefined until the core published it.
 * Changes with every change of the library (renaming, import, files changed on the box).
 */
const useLibraryVersion = () => {
  const { state } = useContext(PubSubContext);
  return state?.[LIBRARY_TOPIC]?.db_update;
};

/** Version of the card database: the time of the last change, undefined until the core published it */
const useCardsVersion = () => {
  const { state } = useContext(PubSubContext);
  return state?.[CARDS_TOPIC];
};

/**
 * Counts how often the version changed while the component is mounted, as dependency for loading data again.
 *
 * The first version (when the page opens, or the web app connects) is no change: the data was just loaded.
 * The core resends the same version to every new subscriber, which isn't a change either.
 */
const useChangeCount = (version) => {
  const lastVersion = useRef(version);
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (version === undefined) return;
    if (lastVersion.current !== undefined && lastVersion.current !== version) {
      setCount(value => value + 1);
    }
    lastVersion.current = version;
  }, [version]);

  return count;
};

/** Number of library changes since the component was mounted, see useChangeCount */
const useLibraryChanges = () => useChangeCount(useLibraryVersion());

/** Number of card database changes since the component was mounted, see useChangeCount */
const useCardsChanges = () => useChangeCount(useCardsVersion());

export {
  useCardsChanges,
  useChangeCount,
  useLibraryChanges,
  useLibraryVersion,
};
