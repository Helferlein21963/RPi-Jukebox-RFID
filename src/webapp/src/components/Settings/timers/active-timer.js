import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Box,
  Button,
  LinearProgress,
  Paper,
  Typography,
} from '@mui/material';

import { toHHMMSS } from '../../../utils/utils';
import TimerIcon from './timer-icon';
import useNow from '../../../utils/use-now';

// A running timer: what it does, live countdown, end time, cancel button
const ActiveTimer = ({ type, timer, onCancel, onExpired }) => {
  const { t, i18n } = useTranslation();
  const now = useNow();
  const [isCancelling, setIsCancelling] = useState(false);

  const remaining = Math.max(0, Math.ceil((timer.endsAt - now) / 1000));
  const progress = timer.totalSeconds ? (remaining / timer.totalSeconds) * 100 : 0;
  const endsAt = new Date(timer.endsAt).toLocaleTimeString(
    i18n.language, { hour: '2-digit', minute: '2-digit' }
  );

  // The core publishes the end; ask again in case that message got lost
  const expired = remaining === 0;
  useEffect(() => {
    if (!expired) return;
    const timeout = setTimeout(onExpired, 3000);
    return () => clearTimeout(timeout);
  }, [expired, onExpired]);

  const handleCancel = async () => {
    setIsCancelling(true);
    await onCancel();
    setIsCancelling(false);
  };

  return (
    <Paper variant="outlined" sx={{ padding: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <TimerIcon type={type} color="primary" fontSize="large" />
        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
          <Typography variant="body2" color="text.secondary">
            {t(`settings.timers.${type}`)}
          </Typography>
          <Typography
            variant="h4"
            component="div"
            sx={{ fontVariantNumeric: 'tabular-nums', lineHeight: 1.2 }}
            aria-live="off"
          >
            {expired ? t('settings.timers.expiring') : toHHMMSS(remaining)}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {t('settings.timers.ends-at', { time: endsAt })}
          </Typography>
        </Box>
        <Button
          variant="outlined"
          color="error"
          onClick={handleCancel}
          disabled={isCancelling}
        >
          {t('settings.timers.cancel')}
        </Button>
      </Box>
      <LinearProgress
        variant="determinate"
        value={progress}
        sx={{ marginTop: 2, borderRadius: 1 }}
      />
    </Paper>
  );
};

export default ActiveTimer;
