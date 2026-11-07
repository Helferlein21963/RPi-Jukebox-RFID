import React from 'react';
import { useTranslation } from 'react-i18next';

import {
  IconButton,
  ListItem,
  ListItemButton,
  ListItemText,
} from '@mui/material';

import NavigateNextIcon from '@mui/icons-material/NavigateNext';

import request from '../../../../utils/request';
import FolderLink from './folder-link';
import FolderTypeAvatar from './folder-type-avatar';
import { DEFAULT_AUDIO_DIR, ROOT_DIRS } from '../../../../config';

const FolderListItem = ({
  dir,
  folder,
  isSelecting,
  registerMusicToCard,
}) => {
  const { t } = useTranslation();
  const { type, name, path } = folder;
  const isDirectory = type === 'directory';

  // Play the whole folder that is shown, starting with this entry.
  // Like the play button of the folder: recursive, except in the root folder (the whole library)
  const playFolderFromItem = () => request('play_folder', {
    folder: dir,
    recursive: !ROOT_DIRS.includes(dir),
    start_song: path,
  });

  const registerItemToCard = () => {
    switch(type) {
      case 'directory': return registerMusicToCard('play_folder', { folder: path, recursive: true });
      case 'file': return registerMusicToCard('play_single', { song_url: path.replace(`${DEFAULT_AUDIO_DIR}/`, '') });
      // TODO: Add missing Podcast
      // TODO: Add missing Stream
      default: return;
    }
  }

  // Outside of card selection, clicking a folder shows its content
  const opensFolder = isDirectory && !isSelecting;
  const buttonProps = opensFolder
    ? { component: FolderLink, data: { dir: path } }
    : { onClick: () => (isSelecting ? registerItemToCard() : playFolderFromItem()) };

  return (
    <ListItem
      disablePadding
      secondaryAction={
        isDirectory
          ? <IconButton
              component={FolderLink}
              data={{ dir: path }}
              edge="end"
              aria-label={t('library.folders.show-folder-content')}
            >
              <NavigateNextIcon />
            </IconButton>
          : undefined
      }
    >
      <ListItemButton {...buttonProps}>
        <FolderTypeAvatar type={type} />
        <ListItemText primary={name} />
      </ListItemButton>
    </ListItem>
  );
}

export default FolderListItem;
