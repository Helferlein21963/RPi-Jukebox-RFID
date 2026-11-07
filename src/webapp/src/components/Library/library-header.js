import React, { useState } from "react";
import {
  useLocation,
  useNavigate,
  useParams,
} from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import {
  Grid,
  IconButton,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
} from "@mui/material";

import SearchIcon from '@mui/icons-material/Search';

const VIEWS = ['albums', 'folders', 'songs'];

const LibraryHeader = ({ musicFilter, setMusicFilter }) => {
  const { search: urlSearch } = useLocation();
  const navigate = useNavigate();
  const { '*': view } = useParams();
  const { t } = useTranslation();
  const [showSearchInput, setShowSearchInput] = useState(false);

  const currentView = VIEWS.find(name => view.startsWith(name)) || 'albums';

  const changeView = (event, path) => {
    // Clicking the active button deselects it: keep the current view then
    if (!path || path === currentView) return;
    localStorage.setItem('libraryLastListView', path);
    navigate(`${path}${urlSearch}`);
  };

  const toggleSearchInput = () => {
    // An invisible filter would keep hiding music, so drop it with the input
    if (showSearchInput) setMusicFilter('');
    setShowSearchInput(!showSearchInput);
  };

  const iconLabel = showSearchInput
    ? t('library.header.search-hide')
    : t('library.header.search-show');

  return (
    <Grid container sx={{ marginBottom: '8px' }}>
      <Grid item
        xs={12}
        sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}
      >
        <IconButton
          aria-label={iconLabel}
          onClick={toggleSearchInput}
          color={showSearchInput ? 'primary' : undefined}
          title={iconLabel}
        >
          <SearchIcon />
        </IconButton>
        {showSearchInput &&
          <TextField
            id="library-search"
            label={t('library.header.search-label')}
            onChange={(event) => setMusicFilter(event.target.value)}
            value={musicFilter}
            variant="outlined"
            size="small"
            autoFocus
            sx={{
              width: '100%',
            }}
          />
        }
        {!showSearchInput &&
          <ToggleButtonGroup
            value={currentView}
            exclusive
            onChange={changeView}
            aria-label={t('library.header.toggle-label')}
            size="small"
            color="primary"
          >
            {VIEWS.map(name => (
              <ToggleButton key={name} value={name}>
                {t(`library.header.${name}`)}
              </ToggleButton>
            ))}
          </ToggleButtonGroup>
        }
      </Grid>
    </Grid>
  );
}

export default LibraryHeader;
