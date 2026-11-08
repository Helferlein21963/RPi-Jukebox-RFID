import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';

import AddIcon from '@mui/icons-material/Add';
import ClearIcon from '@mui/icons-material/Clear';
import SearchIcon from '@mui/icons-material/Search';
import CardsList from './list';
import CircularProgress from '@mui/material/CircularProgress';
import Fab from '@mui/material/Fab';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import IconButton from '@mui/material/IconButton';
import InputAdornment from '@mui/material/InputAdornment';
import TextField from '@mui/material/TextField';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Typography from '@mui/material/Typography';
import { useTheme } from '@mui/material/styles';

import Header from '../Header';
import request from '../../utils/request';
import { useCardsChanges } from '../../utils/use-updates';

const SORT_ORDERS = ['name', 'id'];
const SORT_STORAGE_KEY = 'cardsSortOrder';

// The sort order is a per-browser convenience; storage may be unavailable (e.g. private mode)
const loadSortOrder = () => {
  try {
    const stored = localStorage.getItem(SORT_STORAGE_KEY);
    return SORT_ORDERS.includes(stored) ? stored : 'name';
  } catch {
    return 'name';
  }
};

const storeSortOrder = (sortOrder) => {
  try {
    localStorage.setItem(SORT_STORAGE_KEY, sortOrder);
  } catch {
    // ignore
  }
};

const CardsOverview = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const { t } = useTranslation();

  const [data, setData] = useState({});
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [sortOrder, setSortOrder] = useState(loadSortOrder);
  // Cards registered, edited or deleted (also on other devices, or by renaming folders): load again without a spinner
  const cardsChanges = useCardsChanges();

  const changeSortOrder = (event, value) => {
    // Clicking the active button deselects it: keep the current order then
    if (!value) return;
    setSortOrder(value);
    storeSortOrder(value);
  };

  const openRegisterCard = () => {
    navigate('register');
  };

  useEffect(() => {
    let isMounted = true;
    const loadCardList = async () => {
      const { result, error } = await request('cardsList');
      if (!isMounted) return;
      setIsLoading(false);

      if(result) {
        setData(result);
        setError(null);
      }
      if(error) setError(error);
    }

    loadCardList();
    return () => { isMounted = false; };
  }, [cardsChanges]);

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
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              width: '100%',
              marginTop: '8px',
            }}
          >
            <TextField
              id="cards-search"
              placeholder={t('cards.overview.search-placeholder')}
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
              variant="outlined"
              size="small"
              fullWidth
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
            <ToggleButtonGroup
              value={sortOrder}
              exclusive
              onChange={changeSortOrder}
              aria-label={t('cards.overview.sort-label')}
              size="small"
              color="primary"
              sx={{ flexShrink: 0 }}
            >
              <ToggleButton value="name" title={t('cards.overview.sort-by-name')}>
                {t('cards.overview.sort-name')}
              </ToggleButton>
              <ToggleButton value="id" title={t('cards.overview.sort-by-id')}>
                {t('cards.overview.sort-id')}
              </ToggleButton>
            </ToggleButtonGroup>
          </Box>
        }
        {isLoading
          ? <CircularProgress />
          : <CardsList cardsList={data} filter={filter} sortOrder={sortOrder} />
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
