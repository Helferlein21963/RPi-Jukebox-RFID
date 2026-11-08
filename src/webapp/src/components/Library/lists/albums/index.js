import React, { useEffect, useMemo, useState } from "react";
import { useTranslation } from 'react-i18next';

import {
  CircularProgress,
  Typography,
} from "@mui/material";

import request from '../../../../utils/request';
import { flatByAlbum } from '../../../../utils/utils';

import AlbumList from "./album-list";
import { albumDates, sortAlbums } from '../../sort';

const Albums = ({ musicFilter, sort }) => {
  const { t } = useTranslation();

  const [albums, setAlbums] = useState([]);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  // Date of each album (its newest song), only loaded for sorting by date
  const [dates, setDates] = useState(null);

  const search = ({ albumartist, album }) => {
    if (musicFilter === '') return true;

    const lowerCaseMusicFilter = musicFilter.toLowerCase();

    return albumartist.toLowerCase().includes(lowerCaseMusicFilter) ||
      album.toLowerCase().includes(lowerCaseMusicFilter);
  };

  useEffect(() => {
    const fetchAlbumList = async () => {
      setIsLoading(true);
      const { result, error } = await request('albumList');
      setIsLoading(false);

      if(result) setAlbums(result.reduce(flatByAlbum, []));
      if(error) setError(error);
    }

    fetchAlbumList();
  }, []);

  useEffect(() => {
    if (sort !== 'recent' || dates) return;
    let isMounted = true;
    const fetchDates = async () => {
      const { result } = await request('allSongsList');
      if (isMounted) setDates(albumDates(result || []));
    };
    fetchDates();
    return () => { isMounted = false; };
  }, [sort, dates]);

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
