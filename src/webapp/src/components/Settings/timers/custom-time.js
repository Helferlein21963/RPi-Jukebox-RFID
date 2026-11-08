import React from 'react';
import { useTranslation } from 'react-i18next';

import {
  Box,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';

// Custom timer time: a duration or the time of day the timer ends.
// <input type="time"> opens the time picker of the phone or browser.
const CustomTime = ({
  mode,
  onModeChange,
  value,
  onValueChange,
  preview,
  isValid,
  currentTime,
}) => {
  const { t } = useTranslation();
  const theme = useTheme();

  const handleMode = (event, newMode) => {
    if (newMode) onModeChange(newMode); // Keep one mode selected
  };

  return (
    <Box sx={{ marginTop: 2 }}>
      <ToggleButtonGroup
        value={mode}
        exclusive
        size="small"
        color="primary"
        onChange={handleMode}
        sx={{ marginBottom: 2 }}
      >
        <ToggleButton value="duration" sx={{ textTransform: 'none' }}>
          {t('settings.timers.custom-duration')}
        </ToggleButton>
        <ToggleButton value="clock" sx={{ textTransform: 'none' }}>
          {t('settings.timers.custom-clock')}
        </ToggleButton>
      </ToggleButtonGroup>
      <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
        <TextField
          id="timer-custom-time"
          type="time"
          label={t(`settings.timers.custom-${mode}-label`)}
          value={value}
          onChange={(event) => onValueChange(event.target.value)}
          InputLabelProps={{ shrink: true }}
          inputProps={{ step: 60 }}
          error={!isValid}
          sx={{
            width: 160,
            // Native clock icon and picker in the colors of the theme (else dark on dark)
            '& input': { colorScheme: theme.palette.mode },
            '& input::-webkit-calendar-picker-indicator': { cursor: 'pointer' },
          }}
        />
        <Box>
          <Typography variant="body2" color={isValid ? 'text.secondary' : 'error'}>
            {isValid ? preview : t('settings.timers.custom-invalid')}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ fontVariantNumeric: 'tabular-nums' }}>
            {t('settings.timers.now', { time: currentTime })}
          </Typography>
        </Box>
      </Box>
    </Box>
  );
};

export default CustomTime;
