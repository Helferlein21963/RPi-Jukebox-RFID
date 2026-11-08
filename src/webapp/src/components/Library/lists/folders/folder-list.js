import React, { memo, useState } from 'react';
import { dropLast } from "ramda";
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import {
  Grid,
  IconButton,
  List,
  Typography,
} from '@mui/material';

import EditIcon from '@mui/icons-material/Edit';

import FolderListItem from './folder-list-item';
import FolderListItemBack from './folder-list-item-back';
import RenameDialog from '../../dialogs/rename';
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
  onChanged,
}) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { search: urlSearch } = useLocation();
  const nowPlaying = useNowPlaying();
  // Path of the folder or song being renamed
  const [renamePath, setRenamePath] = useState(undefined);
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

  // The folder shown was renamed: show it under its new name. Otherwise: reload its content
  const onRenamed = (newPath) => {
    const wasShownFolder = renamePath === decodedDir;
    setRenamePath(undefined);
    if (wasShownFolder) {
      navigate(`/library/folders/${encodeURIComponent(newPath)}${urlSearch}`, { replace: true });
    } else {
      onChanged();
    }
  };

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
          <IconButton
            onClick={() => setRenamePath(decodedDir)}
            aria-label={t('library.rename.title-folder')}
          >
            <EditIcon />
          </IconButton>
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
              onRename={setRenamePath}
            />
          );
        })}
      </List>
      {renamePath &&
        <RenameDialog
          open
          path={renamePath}
          onClose={() => setRenamePath(undefined)}
          onRenamed={onRenamed}
        />
      }
    </>
  );
}

export default memo(FolderList);
