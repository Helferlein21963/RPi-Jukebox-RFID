import { useEffect, useState } from 'react';

import request from './request';

// Cover requests, kept until the page is reloaded: lists mount their items again when filtered or sorted
const coverRequests = new Map();

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

  useEffect(() => {
    setCover(undefined);
    if (!key) return undefined;

    let isMounted = true;
    const [command, kwargs] = JSON.parse(key);
    loadCover(command, kwargs).then(url => { if (isMounted) setCover(url); });
    return () => { isMounted = false; };
  }, [key]);

  return cover;
};

export default useCover;
