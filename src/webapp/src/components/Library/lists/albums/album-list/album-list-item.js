import React, { forwardRef } from 'react';
import {
  Link,
  useLocation,
} from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import {
  Avatar,
  ListItem,
  ListItemAvatar,
  ListItemButton,
  ListItemText,
} from '@mui/material';

import noCover from '../../../../../assets/noCover.jpg';

import useCover from '../../../../../utils/use-cover';
import { NowPlayingIcon } from '../../../now-playing';
import { tagToUrl } from '../utils';

const AlbumListItem = ({
  albumartist,
  album,
  isButton = true,
  isCurrent = false,
  isPlaying = false,
}) => {
  const { t } = useTranslation();
  const { search: urlSearch } = useLocation();
  // Cached like the covers of folders and cards: the list mounts its items again when filtered
  const cover = useCover(
    albumartist && album ? ['getAlbumCoverArt', { albumartist, album }] : undefined
  );
  const coverImage = cover || noCover;

  const AlbumLink = forwardRef((props, ref) => {
    const { data } = props;

    // Empty tags stay empty: the song list looks the album up by these values
    const location = `${tagToUrl(data?.albumartist)}/${tagToUrl(data?.album)}${urlSearch}`;

    return <Link ref={ref} to={location} {...props} />
  });

  return (
    <ListItem
      button={isButton}
      component={isButton ? AlbumLink : null}
      data={{ albumartist, album }}
      disablePadding
      key={album}
    >
      <ListItemButton selected={isCurrent}>
        <ListItemAvatar>
          {isCurrent
            ? <Avatar variant="rounded" sx={{ bgcolor: 'primary.main' }}>
                <NowPlayingIcon isPlaying={isPlaying} />
              </Avatar>
            : <Avatar variant="rounded" alt="Cover" src={coverImage} />
          }
        </ListItemAvatar>
        <ListItemText
          primary={album || t('library.albums.unknown-album')}
          secondary={albumartist || null}
        />
      </ListItemButton>
    </ListItem>
  );
}

// Memo: the list re-renders with every player status update
export default React.memo(AlbumListItem);
