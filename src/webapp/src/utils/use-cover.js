import { useEffect, useState } from 'react';

import request from './request';
import { useLibraryChanges, useLibraryVersion } from './use-updates';

// Cover requests, kept until the page is reloaded or the library changes: lists mount their items again
// when filtered or sorted
const coverRequests = new Map();
// Library version the cached covers belong to
let coversVersion;

// After a change of the library a folder may have another first song or a cover where it had none
const forgetOutdatedCovers = (libraryVersion) => {
  if (libraryVersion === undefined || libraryVersion === coversVersion) return;
  if (coversVersion !== undefined) coverRequests.clear();
  coversVersion = libraryVersion;
};

const loadCover = (command, kwargs) => {
  const key = JSON.stringify([command, kwargs]);
  if (!coverRequests.has(key)) {
    const promise = request(command, kwargs).then(({ result, error }) => {
      // Ask again next time, e.g. if the core was not reachable
      if (error) coverRequests.delete(key);
      return result ? `/cover-cache/${result}` : undefined;
    });
    coverRequests.set(key, promise);
  }
  return coverRequests.get(key);
};

/**
 * URL of a cover image, undefined while loading or if there is none
 *
 * @param coverRequest [command, kwargs] of a cover art command (e.g. getFolderCoverArt), undefined for no cover
 */
const useCover = (coverRequest) => {
  const [cover, setCover] = useState(undefined);
  const key = coverRequest ? JSON.stringify(coverRequest) : undefined;
  const libraryVersion = useLibraryVersion();
  const libraryChanges = useLibraryChanges();

  // Another cover: don't show the previous one meanwhile. After a library change it stays until the new one is there
  useEffect(() => {
    setCover(undefined);
  }, [key]);

  useEffect(() => {
    forgetOutdatedCovers(libraryVersion);
  }, [libraryVersion]);

  useEffect(() => {
    if (!key) return undefined;

    let isMounted = true;
    const [command, kwargs] = JSON.parse(key);
    loadCover(command, kwargs).then(url => { if (isMounted) setCover(url); });
    return () => { isMounted = false; };
  }, [key, libraryChanges]);

  return cover;
};

export default useCover;
