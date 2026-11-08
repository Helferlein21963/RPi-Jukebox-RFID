import React, { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router';
import { useTranslation } from 'react-i18next';

import {
  CircularProgress,
  Grid,
  List,
  Typography,
} from '@mui/material';

import request from '../../../../../utils/request';
import { useLibraryChanges } from '../../../../../utils/use-updates';

import SongListHeader from './song-list-header';
import SongListHeadline from './song-list-headline';
import SongListControls from './song-list-controls';
import SongListItem from './song-list-item';
import { isSongPlaying, useNowPlaying } from '../../../now-playing';
import { tagFromUrl } from '../utils';

const SongList = ({
  isSelecting,
  registerMusicToCard,
}) => {
  const { t } = useTranslation();
  const params = useParams();
  const album = tagFromUrl(params.album);
  const artist = tagFromUrl(params.artist);
  const nowPlaying = useNowPlaying();
  const [songs, setSongs] = useState([]);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  // Changes of the library: load the same album again without a spinner
  const libraryChanges = useLibraryChanges();
  const loadedAlbum = useRef(undefined);

  useEffect(() => {
    let isCurrent = true;
    const albumKey = JSON.stringify([artist, album]);
    const getSongList = async () => {
      if (loadedAlbum.current !== albumKey) setIsLoading(true);
      const { result, error } = await request(
        'songList',
        {
          album,
          albumartist: artist,
        }
      );
      if (!isCurrent) return;
      loadedAlbum.current = albumKey;
      setIsLoading(false);

      if(result) {
        setSongs(result);
        setError(null);
      }
      if(error) setError(error);
    }

    getSongList();
    return () => { isCurrent = false; };
  }, [album, artist, libraryChanges]);

  const isAlbumCurrent = songs.some(({ file }) => isSongPlaying(nowPlaying, file));

  return (
    <Grid container id="song-list">
      <SongListHeader />
      <SongListHeadline
        album={album || t('library.albums.unknown-album')}
        artist={artist || t('library.albums.unknown-artist')}
      />
      <SongListControls
        album={album}
        albumartist={artist}
        disabled={songs.length === 0}
        isCurrent={isAlbumCurrent}
        isPlaying={isAlbumCurrent && nowPlaying.isPlaying}
        isSelecting={isSelecting}
        registerMusicToCard={registerMusicToCard}
      />
      <Grid
        container
        spacing={1}
        sx={{
          display: 'flex',
          justifyContent: 'center',
          marginTop: '0'
        }}
      >
        {isLoading
          ? <CircularProgress />
          : <List sx={{ width: '100%' }}>
              {songs.map(song => {
                const isCurrent = isSongPlaying(nowPlaying, song.file);

                return (
                  <SongListItem
                    key={song.file}
                    album={album}
                    albumartist={artist}
                    song={song}
                    isCurrent={isCurrent}
                    isPlaying={isCurrent && nowPlaying.isPlaying}
                    isSelecting={isSelecting}
                    registerMusicToCard={registerMusicToCard}
                  />
                );
              })}
            </List>
        }
        {error &&
          <Typography>{`${t('library.albums.no-songs-in-album')} 🤔`}</Typography>
        }
      </Grid>
    </Grid>
  );
}

export default React.memo(SongList);
