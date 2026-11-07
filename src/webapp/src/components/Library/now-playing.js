import React, { useContext, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { IconButton } from '@mui/material';

import PauseIcon from '@mui/icons-material/Pause';
import PauseCircleFilledRoundedIcon from '@mui/icons-material/PauseCircleFilledRounded';
import PlayCircleFilledRoundedIcon from '@mui/icons-material/PlayCircleFilledRounded';
import VolumeUpIcon from '@mui/icons-material/VolumeUp';

import PlayerContext from '../../context/player/context';
import request from '../../utils/request';

const NOTHING_PLAYING = { isActive: false, isPlaying: false };

/**
 * The song that is playing or paused, as far as the library needs it.
 * Nothing is marked when the player is stopped: the player status keeps keys of
 * songs played before, so its file is only reliable while playing or paused.
 */
const useNowPlaying = () => {
  const { state: { playerstatus } } = useContext(PlayerContext);
  const { state, file, album, albumartist } = playerstatus || {};

  if (!['play', 'pause'].includes(state) || !file) return NOTHING_PLAYING;

  return {
    isActive: true,
    isPlaying: state === 'play',
    // Relative to the music library, like the files of the MPD database
    file,
    album: album || '',
    albumartist: albumartist || '',
  };
};

const isSongPlaying = (nowPlaying, file) => (
  nowPlaying.isActive && !!file && nowPlaying.file === file
);

const isFolderPlaying = (nowPlaying, folder) => (
  nowPlaying.isActive && !!folder && nowPlaying.file.startsWith(`${folder}/`)
);

const isAlbumPlaying = (nowPlaying, albumartist, album) => (
  nowPlaying.isActive && !!album &&
    nowPlaying.album === album && nowPlaying.albumartist === (albumartist || '')
);

// Folder paths of the backend are absolute, MPD's are relative to the library
const toLibraryPath = (path, libraryPath) => (
  libraryPath && path?.startsWith(`${libraryPath}/`)
    ? path.slice(libraryPath.length + 1)
    : path
);

// Absolute path of the music library (undefined until the core answered)
const useMusicLibraryPath = () => {
  const [libraryPath, setLibraryPath] = useState(undefined);

  useEffect(() => {
    let isMounted = true;
    const fetchLibraryPath = async () => {
      const { result } = await request('musicLibraryPath');
      if (result && isMounted) setLibraryPath(result);
    };

    fetchLibraryPath();
    return () => { isMounted = false; };
  }, []);

  return libraryPath;
};

const togglePlayback = () => request('toggle');

const NowPlayingIcon = ({ isPlaying, ...props }) => (
  isPlaying ? <VolumeUpIcon {...props} /> : <PauseIcon {...props} />
);

/**
 * Big play button of a folder or album. If the player is already playing (or paused)
 * a song of it, the button pauses / continues instead of starting again.
 */
const PlayButton = ({ isCurrent, isPlaying, onPlay, disabled, label }) => {
  const { t } = useTranslation();
  const showPause = isCurrent && isPlaying;

  const ariaLabel = isCurrent
    ? t(showPause ? 'player.controls.pause' : 'player.controls.play')
    : label;

  return (
    <IconButton
      aria-label={ariaLabel}
      title={ariaLabel}
      onClick={isCurrent ? togglePlayback : onPlay}
      disabled={disabled}
      size="large"
    >
      {showPause
        ? <PauseCircleFilledRoundedIcon color="primary" style={{ fontSize: 64 }} />
        : <PlayCircleFilledRoundedIcon color="primary" style={{ fontSize: 64 }} />
      }
    </IconButton>
  );
};

export {
  isAlbumPlaying,
  isFolderPlaying,
  isSongPlaying,
  NowPlayingIcon,
  PlayButton,
  togglePlayback,
  toLibraryPath,
  useMusicLibraryPath,
  useNowPlaying,
};
