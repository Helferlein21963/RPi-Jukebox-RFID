import React from 'react';
import { useTranslation } from 'react-i18next';

import {
  ListItem,
  ListItemButton,
  ListItemText,
} from '@mui/material';

import { toHHMMSS } from '../../../../../utils/utils';
import request from '../../../../../utils/request'

const SongListItem = ({
  album,
  albumartist,
  isSelecting,
  registerMusicToCard,
  song,
}) => {
  const { t } = useTranslation();

  const {
    artist,
    duration,
    file,
    title,
  } = song;

  // Play the whole album, starting with this song
  const playAlbumFromSong = () => {
    request('play_album', { albumartist, album, start_song: file })
  }

  const registerSongToCard = () => (
    registerMusicToCard('play_single', { song_url: file })
  );

  return (
    <ListItem disablePadding>
      <ListItemButton
        role={undefined}
        onClick={() => (isSelecting ? registerSongToCard() : playAlbumFromSong())}
      >
        <ListItemText
          primary={title || t('library.albums.unknown-title')}
          secondary={`${artist || t('library.albums.unknown-artist')} • ${toHHMMSS(duration)}`}
        />
      </ListItemButton>
    </ListItem>
  );
}

export default React.memo(SongListItem);
