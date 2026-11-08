import React, { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from 'react-i18next';

import {
  CircularProgress,
  Typography,
} from "@mui/material";

import request from '../../../../utils/request';
import { flatByAlbum } from '../../../../utils/utils';
import { useLibraryChanges } from '../../../../utils/use-updates';

import AlbumList from "./album-list";
import { albumDates, sortAlbums } from '../../sort';

const Albums = ({ musicFilter, sort }) => {
  const { t } = useTranslation();

  const [albums, setAlbums] = useState([]);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  // Date of each album (its newest song), only loaded for sorting by date
  const [dates, setDates] = useState(null);
  // Changes of the library: load again without a spinner, keeping the list until the new one is there
  const libraryChanges = useLibraryChanges();
  const datesLoadedFor = useRef(undefined);

  const search = ({ albumartist, album }) => {
    if (musicFilter === '') return true;

    const lowerCaseMusicFilter = musicFilter.toLowerCase();

    return albumartist.toLowerCase().includes(lowerCaseMusicFilter) ||
      album.toLowerCase().includes(lowerCaseMusicFilter);
  };

  useEffect(() => {
    let isMounted = true;
    const fetchAlbumList = async () => {
      const { result, error } = await request('albumList');
      if (!isMounted) return;
      setIsLoading(false);

      if(result) {
        setAlbums(result.reduce(flatByAlbum, []));
        setError(null);
      }
      if(error) setError(error);
    }

    fetchAlbumList();
    return () => { isMounted = false; };
  }, [libraryChanges]);

  useEffect(() => {
    if (sort !== 'recent' || datesLoadedFor.current === libraryChanges) return;
    let isMounted = true;
    const fetchDates = async () => {
      const { result } = await request('allSongsList');
      if (!isMounted) return;
      datesLoadedFor.current = libraryChanges;
      setDates(albumDates(result || []));
    };
    fetchDates();
    return () => { isMounted = false; };
  }, [sort, libraryChanges]);

  const sortedAlbums = useMemo(
    () => sortAlbums(albums, sort, dates || {}),
    [albums, sort, dates]
  );

  return (
    <>
      {isLoading || (sort === 'recent' && !dates)
        ? <CircularProgress />
        : <AlbumList
            albums={sortedAlbums.filter(search)}
            musicFilter={musicFilter}
      />}
      {error &&
        <Typography>{t('library.loading-error')}</Typography>
      }
    </>
  );
};

export default Albums;
