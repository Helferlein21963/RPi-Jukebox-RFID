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

// Text shown below the card name/ID: the command alias with its arguments, or the full RPC call
const describeCard = ({ from_alias, action, func }, libraryPath) => (
  from_alias
    ? reject(
        isNil,
        flatten([from_alias, action?.args])
      ).map(arg => toDisplayPath(arg, libraryPath)).join(', ')
    : func
);

// Case-insensitive match on card ID, name and description
const matchesFilter = (cardId, card, description, filter) => {
  const needle = filter.trim().toLowerCase();
  if (!needle) return true;

  return [cardId, card.name, description].some(
    value => typeof value === 'string' && value.toLowerCase().includes(needle)
  );
};

const CardsList = ({ cardsList, filter = '' }) => {
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

    const { name } = cardsList[cardId];
    const description = describeCard(cardsList[cardId], libraryPath);

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

  if (!cardsList || Object.keys(cardsList).length === 0) {
    return <Typography>{t('cards.list.no-cards-registered')}</Typography>;
  }

  const cardIds = Object.keys(cardsList).filter(cardId => matchesFilter(
    cardId,
    cardsList[cardId],
    describeCard(cardsList[cardId], libraryPath),
    filter,
  ));

  return (
    cardIds.length > 0
      ? <List sx={{ width: '100%' }}>
          {cardIds.map(ListItemLink)}
        </List>
      : <Typography sx={{ marginTop: '16px' }}>
          {t('cards.list.no-matching-cards', { filter: filter.trim() })}
        </Typography>
  );
}

export { toDisplayPath };
export default React.memo(CardsList);
