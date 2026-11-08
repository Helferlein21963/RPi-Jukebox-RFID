import React, { useEffect, useMemo, useState } from "react";
import { useTranslation } from 'react-i18next';

import {
  Button,
  CircularProgress,
  List,
  Typography,
} from "@mui/material";

import request from '../../../../utils/request';
import { useLibraryChanges } from '../../../../utils/use-updates';

import SongListItem from './song-list-item';
import { isSongPlaying, useNowPlaying } from '../../now-playing';
import { sortSongs } from '../../sort';

// Thousands of list items make the page sluggish on phones: render in pages
const PAGE_SIZE = 200;

const Songs = ({
  musicFilter,
  sort,
  isSelecting,
  registerMusicToCard,
}) => {
  const { t } = useTranslation();
  const nowPlaying = useNowPlaying();

  const [songs, setSongs] = useState([]);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  // Changes of the library: load again without a spinner, keeping the list until the new one is there
  const libraryChanges = useLibraryChanges();

  useEffect(() => {
    let isMounted = true;
    const fetchSongList = async () => {
      const { result, error } = await request('allSongsList');
      if (!isMounted) return;
      setIsLoading(false);

      if(result) {
        setSongs(result);
        setError(null);
      }
      if(error) setError(error);
    }

    fetchSongList();
    return () => { isMounted = false; };
  }, [libraryChanges]);

  useEffect(() => {
    setVisibleCount(PAGE_SIZE);
  }, [musicFilter, sort]);

  const sortedSongs = useMemo(() => sortSongs(songs, sort), [songs, sort]);

  const search = ({ title, artist, album, file }) => {
    if (musicFilter === '') return true;

    const lowerCaseMusicFilter = musicFilter.toLowerCase();

    return [title || file, artist, album].some(
      value => value?.toLowerCase().includes(lowerCaseMusicFilter)
    );
  };

  if (isLoading) return <CircularProgress />;
  if (error) return <Typography>{t('library.loading-error')}</Typography>;

  const filteredSongs = sortedSongs.filter(search);

  if (!filteredSongs.length) {
    if (musicFilter) return <Typography>{`☝️  ${t('library.songs.no-music')}`}</Typography>;
    return <Typography>{`${t('library.songs.empty-library')} 🙈`}</Typography>;
  }

  const remaining = filteredSongs.length - visibleCount;

  return (
    <>
      <List sx={{ width: '100%' }}>
        {filteredSongs.slice(0, visibleCount).map(song => {
          const isCurrent = isSongPlaying(nowPlaying, song.file);

          // Plain booleans, so the memoized items only re-render when they change
          return (
            <SongListItem
              key={song.file}
              song={song}
              isCurrent={isCurrent}
              isPlaying={isCurrent && nowPlaying.isPlaying}
              isSelecting={isSelecting}
              registerMusicToCard={registerMusicToCard}
            />
          );
        })}
      </List>
      {remaining > 0 &&
        <Button
          onClick={() => setVisibleCount(visibleCount + PAGE_SIZE)}
          sx={{ marginBottom: '10px' }}
        >
          {t('library.songs.show-more', { count: remaining })}
        </Button>
      }
    </>
  );
};

export default Songs;
