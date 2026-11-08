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
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
} from "@mui/material";

import CheckIcon from '@mui/icons-material/Check';
import SearchIcon from '@mui/icons-material/Search';
import SortIcon from '@mui/icons-material/Sort';

import { saveLastView, VIEWS } from './views';
import { sortOf, SORTS } from './sort';

const LibraryHeader = ({ musicFilter, setMusicFilter, sorts, onSortChange }) => {
  const { search: urlSearch } = useLocation();
  const navigate = useNavigate();
  const { '*': view } = useParams();
  const { t } = useTranslation();
  const [showSearchInput, setShowSearchInput] = useState(false);
  // Element the sort menu opens at
  const [sortAnchor, setSortAnchor] = useState(null);

  const currentView = VIEWS.find(name => view.startsWith(name)) || VIEWS[0];
  const currentSort = sortOf(sorts, currentView);

  const changeView = (event, path) => {
    // Clicking the active button deselects it: keep the current view then
    if (!path || path === currentView) return;
    saveLastView(path);
    navigate(`${path}${urlSearch}`);
  };

  const chooseSort = (sort) => {
    setSortAnchor(null);
    onSortChange?.(currentView, sort);
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
        {!showSearchInput && onSortChange &&
          <>
            <IconButton
              aria-label={t('library.header.sort-label')}
              title={t('library.header.sort-label')}
              onClick={(event) => setSortAnchor(event.currentTarget)}
              color={currentSort !== SORTS[currentView][0] ? 'primary' : undefined}
              sx={{ marginRight: 'auto' }}
            >
              <SortIcon />
            </IconButton>
            <Menu
              anchorEl={sortAnchor}
              open={!!sortAnchor}
              onClose={() => setSortAnchor(null)}
            >
              {SORTS[currentView].map((sort) => (
                <MenuItem key={sort} selected={sort === currentSort} onClick={() => chooseSort(sort)}>
                  <ListItemIcon>{sort === currentSort && <CheckIcon fontSize="small" />}</ListItemIcon>
                  <ListItemText>{t(`library.header.sort.${sort}`)}</ListItemText>
                </MenuItem>
              ))}
            </Menu>
          </>
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
