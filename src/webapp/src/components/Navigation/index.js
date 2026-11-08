import React, { useContext } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import BottomNavigation from '@mui/material/BottomNavigation';
import BottomNavigationAction from '@mui/material/BottomNavigationAction';
import BookmarksIcon from '@mui/icons-material/Bookmarks';
import CloudDownloadIcon from '@mui/icons-material/CloudDownload';
import HomeIcon from '@mui/icons-material/Home';
import MusicNoteIcon from '@mui/icons-material/MusicNote';
import SettingsIcon from '@mui/icons-material/Settings';

import PubSubContext from '../../context/pubsub/context';
import { pluginIsLoaded } from '../../utils/utils';

// Tabs are identified by their path, so that optional tabs don't shift the others
const tabOfPath = (pathname) => (
  ['/library', '/cards', '/import', '/settings'].find(
    (path) => pathname.startsWith(path)
  ) || '/'
);

export default function Navigation() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const { state } = useContext(PubSubContext);

  const showImport = pluginIsLoaded(state['core.plugins.loaded'], 'ytimport');

  // Five tabs must fit on a narrow phone: the default minimum width is 80px each
  const actionSx = { minWidth: 0, paddingX: 0.5 };

  return (
    <BottomNavigation
      value={tabOfPath(pathname)}
      showLabels
      sx={{
        width: '100%',
        position: 'fixed',
        bottom: '0px',
        height: '65px',
      }}
    >
      <BottomNavigationAction
        component={Link}
        to="/"
        value="/"
        label={t('navigation.start')}
        icon={<HomeIcon />}
        sx={actionSx}
      />
      <BottomNavigationAction
        component={Link}
        to="/library"
        value="/library"
        label={t('navigation.library')}
        icon={<MusicNoteIcon />}
        sx={actionSx}
      />
      <BottomNavigationAction
        component={Link}
        to="/cards"
        value="/cards"
        label={t('navigation.cards')}
        icon={<BookmarksIcon />}
        sx={actionSx}
      />
      {showImport &&
        <BottomNavigationAction
          component={Link}
          to="/import"
          value="/import"
          label={t('navigation.import')}
          icon={<CloudDownloadIcon />}
          sx={actionSx}
        />
      }
      <BottomNavigationAction
        component={Link}
        to="/settings"
        value="/settings"
        label={t('navigation.settings')}
        icon={<SettingsIcon />}
        sx={actionSx}
      />
    </BottomNavigation>
  );
}
