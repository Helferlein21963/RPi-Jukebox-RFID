import React, { memo } from 'react';
import { dropLast } from "ramda";
import { useTranslation } from 'react-i18next';

import {
  Grid,
  List,
  Typography,
} from '@mui/material';

import FolderListItem from './folder-list-item';
import FolderListItemBack from './folder-list-item-back';
import {
  isFolderPlaying,
  isSongPlaying,
  PlayButton,
  toLibraryPath,
  useNowPlaying,
} from '../../now-playing';

import request from '../../../../utils/request';
import { ROOT_DIRS } from '../../../../config';

const FolderList = ({
  dir,
  folders,
  libraryPath,
  isSelecting,
  registerMusicToCard,
}) => {
  const { t } = useTranslation();
  const nowPlaying = useNowPlaying();
  const decodedDir = decodeURIComponent(dir);
  // The backend returns absolute paths, so the library root has two names: './' and its absolute path
  // TODO: ROOT_DIRS should be removed after paths are relative
  const isRootDir = ROOT_DIRS.includes(decodedDir) || decodedDir === libraryPath;

  const getParentDir = () => {
    if (isRootDir) return undefined;

    const parentDir = dropLast(1, decodedDir.split('/')).join('/');
    return parentDir === libraryPath ? './' : parentDir;
  }

  const parentDir = getParentDir();

  const playFolder = () => request('play_folder', { folder: decodedDir, recursive: true });

  // Is the song that is playing in this folder / in this entry (a subfolder or the song itself)?
  const isFolderCurrent = isFolderPlaying(nowPlaying, toLibraryPath(decodedDir, libraryPath));
  const isEntryCurrent = ({ type, path }) => (
    type === 'directory'
      ? isFolderPlaying(nowPlaying, toLibraryPath(path, libraryPath))
      : isSongPlaying(nowPlaying, toLibraryPath(path, libraryPath))
  );

  return (
    <>
      {!isRootDir && !isSelecting &&
        <Grid container sx={{ padding: '0 8px', alignItems: 'center', flexWrap: 'nowrap' }}>
          <Typography
            variant="h6"
            sx={{ flexGrow: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
          >
            {decodedDir.split('/').pop()}
          </Typography>
          <PlayButton
            isCurrent={isFolderCurrent}
            isPlaying={isFolderCurrent && nowPlaying.isPlaying}
            onPlay={playFolder}
            label={t('library.folders.play-folder')}
          />
        </Grid>
      }
      <List sx={{ width: '100%' }}>
        {parentDir &&
          <FolderListItemBack
            dir={parentDir}
          />
        }
        {folders.map((folder, key) => {
          const isCurrent = isEntryCurrent(folder);

          return (
            <FolderListItem
              key={key}
              dir={decodedDir}
              isRootDir={isRootDir}
              folder={folder}
              isCurrent={isCurrent}
              isPlaying={isCurrent && nowPlaying.isPlaying}
              isSelecting={isSelecting}
              registerMusicToCard={registerMusicToCard}
            />
          );
        })}
      </List>
    </>
  );
}

export default memo(FolderList);
