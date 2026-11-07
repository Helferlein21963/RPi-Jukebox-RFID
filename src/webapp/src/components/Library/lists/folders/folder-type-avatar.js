import React from 'react';

import {
  Avatar,
  ListItemAvatar,
} from '@mui/material';

import FolderIcon from '@mui/icons-material/Folder';
import MusicNoteIcon from '@mui/icons-material/MusicNote';
import PodcastsIcon from '@mui/icons-material/Podcasts';
import RadioIcon from '@mui/icons-material/Radio';

import { NowPlayingIcon } from '../../now-playing';

// isCurrent: the song that is playing is this entry or in this folder
const FolderTypeAvatar = ({ type, isCurrent = false, isPlaying = false }) => (
  <ListItemAvatar>
    {isCurrent
      ? <Avatar sx={{ bgcolor: 'primary.main' }}>
          <NowPlayingIcon isPlaying={isPlaying} />
        </Avatar>
      : <Avatar>
          {type === 'directory' && <FolderIcon />}
          {type === 'file' && <MusicNoteIcon />}
          {type === 'podcast' && <PodcastsIcon />}
          {type === 'stream' && <RadioIcon />}
        </Avatar>
    }
  </ListItemAvatar>
);

export default FolderTypeAvatar;
