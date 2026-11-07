import React from 'react';
import { useTranslation } from 'react-i18next';

import {
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
} from '@mui/material';

import { NowPlayingIcon, togglePlayback } from '../../../now-playing';
import { toHHMMSS } from '../../../../../utils/utils';
import request from '../../../../../utils/request'

const SongListItem = ({
  album,
  albumartist,
  isCurrent,
  isPlaying,
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
    track,
  } = song;

  // Track numbers can look like '3/12'
  const trackNumber = parseInt(track, 10);

  // Play the whole album, starting with this song. The current song: pause, or continue
  const playAlbumFromSong = () => (
    isCurrent
      ? togglePlayback()
      : request('play_album', { albumartist, album, start_song: file })
  );

  const registerSongToCard = () => (
    registerMusicToCard('play_single', { song_url: file })
  );

  return (
    <ListItem disablePadding>
      <ListItemButton
        role={undefined}
        selected={isCurrent}
        onClick={() => (isSelecting ? registerSongToCard() : playAlbumFromSong())}
      >
        <ListItemIcon sx={{ minWidth: '40px' }}>
          {isCurrent
            ? <NowPlayingIcon isPlaying={isPlaying} color="primary" />
            : <Typography color="textSecondary">{isNaN(trackNumber) ? '' : trackNumber}</Typography>
          }
        </ListItemIcon>
        <ListItemText
          primary={title || t('library.albums.unknown-title')}
          secondary={`${artist || t('library.albums.unknown-artist')} • ${toHHMMSS(duration)}`}
        />
      </ListItemButton>
    </ListItem>
  );
}

export default React.memo(SongListItem);
