import React from 'react';
import { useLocation } from 'react-router-dom';

import { Box } from '@mui/material';

import Clock from '../Clock';
import Volume from '../Player/volume';

// Bar at the top of every page: volume of the box (left) and the clock (right).
// The start page has the large volume slider already, so the small one is left out there.
const TopBar = () => {
  const { pathname } = useLocation();
  const showVolume = pathname !== '/';

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        paddingLeft: 1,
      }}
    >
      {showVolume && (
        <Box sx={{ flex: 1, maxWidth: 280, minWidth: 0 }}>
          <Volume compact />
        </Box>
      )}
      <Box sx={{ marginLeft: 'auto' }}>
        <Clock />
      </Box>
    </Box>
  );
};

export default TopBar;
