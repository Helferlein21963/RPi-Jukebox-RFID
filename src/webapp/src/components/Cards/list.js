import React, { forwardRef } from 'react';
import { Link } from 'react-router-dom';
import { flatten, isNil, reject } from 'ramda';
import { useTranslation } from 'react-i18next';

import {
  Avatar,
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  Typography
} from '@mui/material';

import BookmarkIcon from '@mui/icons-material/Bookmark';

import { toLibraryPath, useMusicLibraryPath } from '../Library/now-playing';
import { DEFAULT_AUDIO_DIR } from '../../config';

// Folders inside the music library are shown relative to it
const toDisplayPath = (path, libraryPath) => (
  typeof path === 'string'
    ? toLibraryPath(path, libraryPath).replace(`${DEFAULT_AUDIO_DIR}/`, '')
    : path
);

const CardsList = ({ cardsList }) => {
  const { t } = useTranslation();
  const libraryPath = useMusicLibraryPath();

  const ListItemLink = (cardId) => {
    const EditCardLink = forwardRef((props, ref) => {
      const { data } = props;
      const location = {
        pathname: `/cards/${data.id}/edit`,
        state: data,
      };

      return <Link ref={ref} to={location} {...props} />
    });

    const { from_alias, action, func, name } = cardsList[cardId];
    const description = from_alias
      ? reject(
          isNil,
          flatten([from_alias, action?.args])
        ).map(arg => toDisplayPath(arg, libraryPath)).join(', ')
      : func

    return (
      <ListItem
        button
        component={EditCardLink}
        data={{ id: cardId, ...cardsList[cardId] }}
        key={cardId}
      >
        <ListItemAvatar>
          <Avatar>
            <BookmarkIcon />
          </Avatar>
        </ListItemAvatar>
        <ListItemText
          primary={
            name
              ? <>
                  {name}
                  <Typography
                    component="span"
                    variant="body2"
                    color="text.secondary"
                    sx={{ marginLeft: '8px' }}
                  >
                    {cardId}
                  </Typography>
                </>
              : cardId
          }
          secondary={description}
        />
      </ListItem>
    );
  }

  return (
    cardsList && Object.keys(cardsList).length > 0
      ? <List sx={{ width: '100%' }}>
          {Object.keys(cardsList).map(ListItemLink)}
        </List>
      : <Typography>{t('cards.list.no-cards-registered')}</Typography>
  );
}

export { toDisplayPath };
export default React.memo(CardsList);
