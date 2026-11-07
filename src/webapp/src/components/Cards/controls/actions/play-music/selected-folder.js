import React from 'react';
import { List } from '@mui/material';

import {
  ListItem,
  ListItemText,
} from '@mui/material';

import NoMusicSelected from './no-music-selected';
import FolderTypeAvatar from '../../../../Library/lists/folders/folder-type-avatar';
import { useMusicLibraryPath } from '../../../../Library/now-playing';
import { toDisplayPath } from '../../../list';

const SelectedFolder = ({ values: [folder] }) => {
  // TODO: Implement type correctly
  const type = 'directory';
  const libraryPath = useMusicLibraryPath();

  if (folder) {
    return (
      <List sx={{ width: '100%', margin: '10px' }}>
        <ListItem disablePadding>
          <FolderTypeAvatar type={type} />
          <ListItemText primary={toDisplayPath(folder, libraryPath)} />
        </ListItem>
      </List>
    );
  }

  return <NoMusicSelected />
};

export default SelectedFolder;
