import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';

import AddIcon from '@mui/icons-material/Add';
import ClearIcon from '@mui/icons-material/Clear';
import SearchIcon from '@mui/icons-material/Search';
import CardsList from './list';
import CircularProgress from '@mui/material/CircularProgress';
import Fab from '@mui/material/Fab';
import Grid from '@mui/material/Grid';
import IconButton from '@mui/material/IconButton';
import InputAdornment from '@mui/material/InputAdornment';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useTheme } from '@mui/material/styles';

import Header from '../Header';
import request from '../../utils/request';

const CardsOverview = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const { t } = useTranslation();

  const [data, setData] = useState({});
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState('');

  const openRegisterCard = () => {
    navigate('register');
  };

  useEffect(() => {
    const loadCardList = async () => {
      setIsLoading(true);
      const { result, error } = await request('cardsList');
      setIsLoading(false);

      if(result) setData(result);
      if(error) setError(error);
    }

    loadCardList();
  }, []);

  return (
    <Grid container id="cards">
      <Header title={t('cards.overview.cards')} />
      <Grid
        container
        spacing={1}
        sx={{
          display: 'flex',
          justifyContent: 'center',
        }}
      >
        {!isLoading && Object.keys(data).length > 0 &&
          <TextField
            id="cards-search"
            placeholder={t('cards.overview.search-placeholder')}
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            variant="outlined"
            size="small"
            fullWidth
            sx={{ marginTop: '8px' }}
            inputProps={{ 'aria-label': t('cards.overview.search-label') }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              ),
              endAdornment: filter && (
                <InputAdornment position="end">
                  <IconButton
                    aria-label={t('cards.overview.search-clear')}
                    title={t('cards.overview.search-clear')}
                    edge="end"
                    size="small"
                    onClick={() => setFilter('')}
                  >
                    <ClearIcon />
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />
        }
        {isLoading
          ? <CircularProgress />
          : <CardsList cardsList={data} filter={filter} />
        }
        {error &&
          <Typography>{t('cards.overview.loading-error')}</Typography>
        }
      </Grid>
      <Fab
        aria-label={t('cards.overview.register-card')}
        color="primary"
        onClick={openRegisterCard}
        sx={{
          position: 'fixed',
          bottom: { xs: '76px', sm: '76px', md: '76px' },
          right: { xs: theme.spacing(1), sm: theme.spacing(2), md: theme.spacing(2) },
          zIndex: 1000,
        }}
      >
        <AddIcon />
      </Fab>
    </Grid>
  );
};

export default CardsOverview;
