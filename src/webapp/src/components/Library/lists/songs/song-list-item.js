import React from 'react';
import { useTranslation } from 'react-i18next';

import {
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
} from '@mui/material';

import MusicNoteIcon from '@mui/icons-material/MusicNote';

import { NowPlayingIcon, togglePlayback } from '../../now-playing';
import { toHHMMSS } from '../../../../utils/utils';
import request from '../../../../utils/request';

const SongListItem = ({
  isCurrent,
  isPlaying,
  isSelecting,
  registerMusicToCard,
  song,
}) => {
  const { t } = useTranslation();

  const {
    album,
    artist,
    duration,
    file,
    title,
  } = song;

  // Play only this song. The current song: pause, or continue
  const playSong = () => (
    isCurrent ? togglePlayback() : request('play_single', { song_url: file })
  );

  const registerSongToCard = () => (
    registerMusicToCard('play_single', { song_url: file })
  );

  const details = [
    artist || t('library.albums.unknown-artist'),
    album,
    duration ? toHHMMSS(Number(duration)) : '',
  ].filter(Boolean).join(' • ');

  return (
    <ListItem disablePadding>
      <ListItemButton
        role={undefined}
        selected={isCurrent}
        onClick={() => (isSelecting ? registerSongToCard() : playSong())}
      >
        <ListItemIcon sx={{ minWidth: '40px' }}>
          {isCurrent
            ? <NowPlayingIcon isPlaying={isPlaying} color="primary" />
            : <MusicNoteIcon sx={{ color: 'text.secondary' }} />
          }
        </ListItemIcon>
        <ListItemText
          primary={title || file.split('/').pop() || t('library.albums.unknown-title')}
          secondary={details}
        />
      </ListItemButton>
    </ListItem>
  );
};

export default React.memo(SongListItem);
