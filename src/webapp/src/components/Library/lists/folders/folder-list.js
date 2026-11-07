import React, { memo } from 'react';
import { dropLast } from "ramda";
import { useTranslation } from 'react-i18next';

import {
  Grid,
  IconButton,
  List,
  Typography,
} from '@mui/material';

import PlayCircleFilledRoundedIcon from '@mui/icons-material/PlayCircleFilledRounded';

import FolderListItem from './folder-list-item';
import FolderListItemBack from './folder-list-item-back';

import request from '../../../../utils/request';
import { ROOT_DIRS } from '../../../../config';

const FolderList = ({
  dir,
  folders,
  isSelecting,
  registerMusicToCard,
}) => {
  const { t } = useTranslation();
  const decodedDir = decodeURIComponent(dir);
  // TODO: ROOT_DIRS should be removed after paths are relative
  const isRootDir = ROOT_DIRS.includes(decodedDir);

  const getParentDir = () => {
    if (isRootDir) return undefined;

    const parentDir = dropLast(1, decodedDir.split('/')).join('/');
    return parentDir;
  }

  const parentDir = getParentDir();

  const playFolder = () => request('play_folder', { folder: decodedDir, recursive: true });

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
            aria-label={t('library.folders.play-folder')}
            onClick={playFolder}
            size="large"
          >
            <PlayCircleFilledRoundedIcon color="primary" style={{ fontSize: 64 }} />
          </IconButton>
        </Grid>
      }
      <List sx={{ width: '100%' }}>
        {parentDir &&
          <FolderListItemBack
            dir={parentDir}
          />
        }
        {folders.map((folder, key) =>
          <FolderListItem
            key={key}
            dir={decodedDir}
            folder={folder}
            isSelecting={isSelecting}
            registerMusicToCard={registerMusicToCard}
          />
        )}
      </List>
    </>
  );
}

export default memo(FolderList);
