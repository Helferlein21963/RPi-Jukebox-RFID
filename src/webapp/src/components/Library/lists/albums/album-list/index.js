import React from 'react';
import { useTranslation } from 'react-i18next';

import {
  List,
  Typography,
} from '@mui/material';

import AlbumListItem from './album-list-item';
import { isAlbumPlaying, useNowPlaying } from '../../../now-playing';

const AlbumList = ({ albums, musicFilter }) => {
  const { t } = useTranslation();
  const nowPlaying = useNowPlaying();

  if (albums?.length) {
    return (
      <List sx={{ width: '100%' }}>
        {albums.map(({ albumartist, album }, i) => {
          const isCurrent = isAlbumPlaying(nowPlaying, albumartist, album);

          return (
            <AlbumListItem
              key={i}
              albumartist={albumartist}
              album={album}
              isCurrent={isCurrent}
              isPlaying={isCurrent && nowPlaying.isPlaying}
            />
          );
        })}
      </List>
    );
  }

  if (musicFilter) return <Typography>{`☝️  ${t('library.albums.no-music')}`}</Typography>
  return <Typography>{`${t('library.albums.empty-library')} 🙈`}</Typography>
}

export default React.memo(AlbumList);
