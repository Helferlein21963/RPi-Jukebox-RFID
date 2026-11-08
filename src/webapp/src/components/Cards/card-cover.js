import React from 'react';

import { Avatar } from '@mui/material';
import BookmarkIcon from '@mui/icons-material/Bookmark';

import useCover from '../../utils/use-cover';
import { NowPlayingIcon } from '../Library/now-playing';
import { cardMusic } from './card-music';

// The request for the cover of a card's music: [command, kwargs], undefined for cards without music
const coverRequest = (music) => {
  if (!music) return undefined;
  if (music.folder) return ['getFolderCoverArt', { folder: music.folder }];
  if (music.song) return ['getSingleCoverArt', { song_url: music.song }];
  return ['getAlbumCoverArt', { albumartist: music.albumartist, album: music.album }];
};

/**
 * Cover of the folder, song or album the card plays, the card icon for cards without music or cover.
 * The card of the current playback shows play / pause like the library.
 */
const CardAvatar = ({ card, libraryPath, isCurrent = false, isPlaying = false }) => {
  // Wait for the library path: otherwise the same folder would be asked for twice (absolute, then relative)
  const cover = useCover(libraryPath ? coverRequest(cardMusic(card, libraryPath)) : undefined);

  if (isCurrent) {
    // Square like a cover, round like the card icon
    return (
      <Avatar variant={cover ? 'rounded' : 'circular'} sx={{ bgcolor: 'primary.main' }}>
        <NowPlayingIcon isPlaying={isPlaying} />
      </Avatar>
    );
  }

  return cover
    ? <Avatar variant="rounded" alt="Cover" src={cover} />
    : <Avatar><BookmarkIcon /></Avatar>;
};

export {
  CardAvatar,
  coverRequest,
};
