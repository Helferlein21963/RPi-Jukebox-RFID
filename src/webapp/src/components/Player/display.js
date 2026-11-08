import React, { useContext } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import PlayerContext from '../../context/player/context';
import { useCurrentCard } from './current-card';

import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';

import BookmarkIcon from '@mui/icons-material/Bookmark';

const dontBreak = {
  whiteSpace: 'nowrap',
  width: '100%',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
};

// Name and ID of the card belonging to the current playback, links to the card's settings
const CurrentCard = ({ card: { id, name } }) => {
  const { t } = useTranslation();

  return (
    <Typography
      component={Link}
      to={`/cards/${encodeURIComponent(id)}/edit`}
      title={t('player.display.card-edit')}
      variant="body2"
      color="textSecondary"
      sx={{
        ...dontBreak,
        display: 'flex',
        alignItems: 'center',
        marginTop: '4px',
        textDecoration: 'none',
      }}
    >
      <BookmarkIcon fontSize="small" sx={{ marginRight: '4px', flexShrink: 0 }} />
      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {name
          ? <>{name}<span style={{ marginLeft: '8px', opacity: 0.7 }}>{id}</span></>
          : t('player.display.card-id', { id })
        }
      </span>
    </Typography>
  );
};

const Display = () => {
  const { t } = useTranslation();
  const { state: { playerstatus } } = useContext(PlayerContext);
  const currentCard = useCurrentCard();

  return (
    <Grid container>
      <Typography sx={dontBreak} component="h5" variant="h5">
        {playerstatus?.songid
          ? (playerstatus?.title || t('player.display.unknown-title'))
          : t('player.display.no-song-in-queue')
        }
      </Typography>
      <Typography sx={dontBreak} variant="subtitle1" color="textSecondary">
        {playerstatus?.songid && (playerstatus?.artist || t('player.display.unknown-artist')) }
        <span sx={{ marginLeft: '5px', marginRight: '5px' }}>&bull;</span>
        {playerstatus?.songid && (playerstatus?.album || playerstatus?.file) }
      </Typography>
      {currentCard && <CurrentCard card={currentCard} />}
    </Grid>
  );
};

export default Display;
