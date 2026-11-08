import React from 'react';
import { useTranslation } from 'react-i18next';

import {
  Avatar,
  Card,
  CardContent,
  CardHeader,
  Grid,
  TextField,
  Typography
} from '@mui/material';
import BookmarkIcon from '@mui/icons-material/Bookmark';

import Header from '../Header';
import ActionsControls from './controls/actions-controls';
import ControlsSelector from './controls/controls-selector';

const InfoNoCardSwiped = () => {
  const { t } = useTranslation();

  return (
    <Typography>
      {`⚠️ ${t('cards.form.no-card-swiped')}`}
    </Typography>
  );
};

const CardsForm = ({
  title,
  cardId,
  actionData,
  setActionData,
  cardName,
  setCardName,
}) => {
  const { t } = useTranslation();

  return (
    <>
      <Header title={title} backLink="/cards" />
      <Grid container>
        <Grid item xs={12}>
          <Card elevation={0}>
            <CardHeader
              avatar={
                <Avatar aria-label={t('cards.form.no-card-swiped')}>
                  <BookmarkIcon />
                </Avatar>
              }
              title={
                cardName
                  ? cardName
                  : (cardId || t('cards.form.no-card-id'))
              }
              subheader={cardName && cardId ? t('cards.form.card-id', { cardId }) : undefined}
            />
            <CardContent>
              {cardId &&
                <>
                  <Grid
                    container
                    direction="row"
                    alignItems="center"
                    sx={{ marginBottom: '20px' }}
                  >
                    <Grid item xs={5}>
                      <Typography>
                        {t('cards.form.card-name')}
                      </Typography>
                    </Grid>
                    <Grid item xs={7}>
                      <TextField
                        fullWidth
                        size="small"
                        variant="standard"
                        value={cardName || ''}
                        onChange={(event) => setCardName(event.target.value)}
                        placeholder={t('cards.form.card-name-placeholder')}
                        inputProps={{
                          'aria-label': t('cards.form.card-name'),
                          maxLength: 60,
                        }}
                      />
                    </Grid>
                  </Grid>
                  <Grid container direction="row" alignItems="center">
                    <ControlsSelector
                      actionData={actionData}
                      setActionData={setActionData}
                      cardId={cardId}
                    />
                  </Grid>
                  <ActionsControls
                    actionData={actionData}
                    cardId={cardId}
                    cardName={cardName}
                  />
                </>
              }
              {!cardId && <InfoNoCardSwiped />}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </>
  );
};



export default CardsForm;
