import React from 'react';
import { useTranslation } from 'react-i18next';

import { Box, Typography } from '@mui/material';

import useNow from '../../utils/use-now';

// Date and time of this device, shown at the top of every page
const Clock = () => {
  const { i18n } = useTranslation();
  const now = new Date(useNow());

  const date = now.toLocaleDateString(i18n.language, { weekday: 'short', day: 'numeric', month: 'short' });
  const time = now.toLocaleTimeString(i18n.language, { hour: '2-digit', minute: '2-digit' });

  return (
    <Box
      component="time"
      dateTime={now.toISOString()}
      sx={{
        display: 'flex',
        justifyContent: 'flex-end',
        alignItems: 'baseline',
        gap: 1,
        paddingX: 2,
        paddingTop: 0.5,
        minHeight: 28,
      }}
    >
      <Typography variant="body2" color="text.secondary">
        {date}
      </Typography>
      <Typography variant="body2" sx={{ fontWeight: 500, fontVariantNumeric: 'tabular-nums' }}>
        {time}
      </Typography>
    </Box>
  );
};

export default Clock;
