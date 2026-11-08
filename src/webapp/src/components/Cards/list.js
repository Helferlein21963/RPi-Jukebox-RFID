import React, { forwardRef } from 'react';
import { Link } from 'react-router-dom';
import { flatten, isNil, reject } from 'ramda';
import { useTranslation } from 'react-i18next';

import {
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  Typography
} from '@mui/material';

import { useMusicLibraryPath } from '../Library/now-playing';
import { useCurrentCardOf } from '../Player/current-card';
import { CardAvatar } from './card-cover';
import { toDisplayPath } from './card-music';

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

const compareText = (a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' });

// 'name': named cards alphabetically, then cards without a name by ID; 'id': all cards by ID
const sortCardIds = (cardIds, cardsList, sortOrder) => (
  [...cardIds].sort((a, b) => {
    if (sortOrder === 'name') {
      const nameA = cardsList[a].name;
      const nameB = cardsList[b].name;
      if (nameA && nameB) return compareText(nameA, nameB) || compareText(a, b);
      if (nameA || nameB) return nameA ? -1 : 1;
    }
    return compareText(a, b);
  })
);

// Defined once: a component created while rendering would mount the list items again on every
// render, which happens often (the current card follows the player status)
const EditCardLink = forwardRef((props, ref) => {
  const { data } = props;
  const location = {
    pathname: `/cards/${data.id}/edit`,
    state: data,
  };

  return <Link ref={ref} to={location} {...props} />
});

const CardsList = ({ cardsList, filter = '', sortOrder = 'name' }) => {
  const { t } = useTranslation();
  const libraryPath = useMusicLibraryPath();
  // Marked with play / pause, like the library
  const currentCard = useCurrentCardOf(cardsList, libraryPath);

  const ListItemLink = (cardId) => {
    const { name } = cardsList[cardId];
    const description = describeCard(cardsList[cardId], libraryPath);
    const isCurrent = currentCard?.id === cardId;

    return (
      <ListItem
        button
        component={EditCardLink}
        data={{ id: cardId, ...cardsList[cardId] }}
        key={cardId}
        selected={isCurrent}
      >
        <ListItemAvatar>
          <CardAvatar
            card={cardsList[cardId]}
            libraryPath={libraryPath}
            isCurrent={isCurrent}
            isPlaying={isCurrent && currentCard.isPlaying}
          />
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

  const cardIds = sortCardIds(
    Object.keys(cardsList).filter(cardId => matchesFilter(
      cardId,
      cardsList[cardId],
      describeCard(cardsList[cardId], libraryPath),
      filter,
    )),
    cardsList,
    sortOrder,
  );

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

export default React.memo(CardsList);
