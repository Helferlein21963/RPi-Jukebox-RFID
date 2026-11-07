import React, { useContext, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
} from '@mui/material';

import PauseIcon from '@mui/icons-material/Pause';
import VolumeUpIcon from '@mui/icons-material/VolumeUp';

import PlayerContext from '../../context/player/context';
import request from '../../utils/request';
import { toHHMMSS } from '../../utils/utils';

const fileName = (file = '') => file.split('/').pop();

const Playlist = () => {
  const { t } = useTranslation();
  const { state: { playerstatus } } = useContext(PlayerContext);
  // playlist is MPD's version number of the queue: it changes whenever the queue changes
  const { playlist: version, song: currentPos, state } = playerstatus || {};

  const [songs, setSongs] = useState([]);

  useEffect(() => {
    // Set when the queue changes again before the request returns, so a late reply
    // can't overwrite the newer playlist
    let outdated = false;

    const getPlaylist = async () => {
      const { result } = await request('playlistinfo');
      if (!outdated) setSongs(Array.isArray(result) ? result : []);
    };

    getPlaylist();

    return () => { outdated = true; };
  }, [version]);

  if (!songs.length) return null;

  // By MPD song id, not position: a tap on an outdated list (e.g. right after a card swipe) does nothing
  // instead of playing a song of the new playlist
  const playSong = (pos, id) => {
    if (pos !== currentPos) return request('play_song', { songid: id });
    // The current song: pause, or continue where it was paused / stopped
    return request('toggle');
  };

  return (
    <>
      <Typography variant="h6" sx={{ marginTop: '20px' }}>
        {t('player.playlist.title', { count: songs.length })}
      </Typography>
      <List dense sx={{ width: '100%' }}>
        {songs.map(({ pos, id, file, title, name, artist, duration }) => {
          const isCurrent = pos === currentPos;
          const secondary = [artist, duration && toHHMMSS(duration)].filter(Boolean).join(' • ');

          return (
            <ListItem key={`${pos}-${file}`} disablePadding>
              <ListItemButton selected={isCurrent} onClick={() => playSong(pos, id)}>
                <ListItemIcon sx={{ minWidth: '40px' }}>
                  {isCurrent
                    ? (state === 'play' ? <VolumeUpIcon /> : <PauseIcon />)
                    : <Typography color="textSecondary">{Number(pos) + 1}</Typography>
                  }
                </ListItemIcon>
                <ListItemText
                  primary={title || name || fileName(file) || t('player.playlist.unknown-title')}
                  secondary={secondary || undefined}
                />
              </ListItemButton>
            </ListItem>
          );
        })}
      </List>
    </>
  );
};

export default Playlist;
