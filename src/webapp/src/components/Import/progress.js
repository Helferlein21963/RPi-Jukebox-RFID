import React from 'react';
import { useTranslation } from 'react-i18next';

import {
  Alert,
  Box,
  Button,
  Grid,
  LinearProgress,
  Typography,
} from '@mui/material';

import request from '../../utils/request';
import FailedTracks from './failed-tracks';

const ImportProgress = ({ status }) => {
  const { t } = useTranslation();
  const {
    folder,
    current = 0,
    total = 0,
    track_title: trackTitle,
    phase = 'download',
    percent = 0,
    failed = [],
  } = status;

  const overall = total
    ? ((Math.max(current - 1, 0) + percent / 100) / total) * 100
    : 0;

  return (
    <Grid container direction="column" spacing={2}>
      <Grid item>
        <Typography variant="subtitle1">
          {t('import.progress.title', { folder })}
        </Typography>
      </Grid>
      <Grid item>
        <Typography variant="body2" noWrap>
          {t('import.progress.track', { current, total })}: {trackTitle}
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <LinearProgress variant="determinate" value={percent} sx={{ flexGrow: 1 }} />
          <Typography variant="caption" color="text.secondary" sx={{ minWidth: 36 }}>
            {Math.round(percent)} %
          </Typography>
        </Box>
        <Typography variant="caption" color="text.secondary">
          {t(`import.progress.${phase}`)}
        </Typography>
      </Grid>
      <Grid item>
        <Typography variant="body2">{t('import.progress.overall')}</Typography>
        <LinearProgress variant="determinate" value={overall} color="secondary" />
      </Grid>
      {failed.length > 0 &&
        <Grid item>
          <FailedTracks failed={failed} />
        </Grid>
      }
      <Grid item>
        <Alert severity="info">{t('import.progress.hint')}</Alert>
      </Grid>
      <Grid item>
        <Grid container justifyContent="flex-end">
          <Button color="error" onClick={() => request('ytimportCancel')}>
            {t('import.cancel')}
          </Button>
        </Grid>
      </Grid>
    </Grid>
  );
};

export default ImportProgress;
