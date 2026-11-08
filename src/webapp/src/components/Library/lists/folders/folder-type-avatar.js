import React from 'react';

import {
  Avatar,
  ListItemAvatar,
} from '@mui/material';

import FolderIcon from '@mui/icons-material/Folder';
import MusicNoteIcon from '@mui/icons-material/MusicNote';
import PodcastsIcon from '@mui/icons-material/Podcasts';
import RadioIcon from '@mui/icons-material/Radio';

import useCover from '../../../../utils/use-cover';
import { NowPlayingIcon } from '../../now-playing';

/**
 * Icon of a library entry. Folders show their cover (the one of their first song) if given a path.
 *
 * isCurrent: the song that is playing is this entry or in this folder
 */
const FolderTypeAvatar = ({ type, path, isCurrent = false, isPlaying = false }) => {
  const cover = useCover(type === 'directory' && path ? ['getFolderCoverArt', { folder: path }] : undefined);
  // Covers are square, like in the album list
  const variant = cover ? 'rounded' : 'circular';

  return (
    <ListItemAvatar>
      {isCurrent
        ? <Avatar variant={variant} sx={{ bgcolor: 'primary.main' }}>
            <NowPlayingIcon isPlaying={isPlaying} />
          </Avatar>
        : cover
          ? <Avatar variant={variant} alt="Cover" src={cover} />
          : <Avatar>
              {type === 'directory' && <FolderIcon />}
              {type === 'file' && <MusicNoteIcon />}
              {type === 'podcast' && <PodcastsIcon />}
              {type === 'stream' && <RadioIcon />}
            </Avatar>
      }
    </ListItemAvatar>
  );
};

export default FolderTypeAvatar;
