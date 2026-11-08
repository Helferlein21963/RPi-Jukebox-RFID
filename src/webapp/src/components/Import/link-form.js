import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Alert,
  Button,
  CircularProgress,
  Grid,
  TextField,
  Typography,
} from '@mui/material';

import request from '../../utils/request';

const LinkForm = ({ status, disabled }) => {
  const { t } = useTranslation();
  const [url, setUrl] = useState(status?.url || '');
  const [error, setError] = useState(null);
  const isFetching = status?.state === 'fetching';

  // Show the link of a job that was started elsewhere (other device, page reload)
  useEffect(() => {
    if (status?.url) setUrl(status.url);
  }, [status?.url]);

  const fetchInfo = async (event) => {
    event.preventDefault();
    setError(null);
    const { error } = await request('ytimportFetchInfo', { url: url.trim() });
    if (error) setError(String(error));
  };

  return (
    <form onSubmit={fetchInfo}>
      <Grid container spacing={1} alignItems="center">
        <Grid item xs>
          <TextField
            fullWidth
            size="small"
            type="url"
            label={t('import.link.label')}
            placeholder="https://www.youtube.com/..."
            value={url}
            disabled={disabled}
            onChange={(event) => setUrl(event.target.value)}
          />
        </Grid>
        <Grid item>
          <Button
            type="submit"
            variant="contained"
            disabled={disabled || !url.trim()}
          >
            {t('import.link.load')}
          </Button>
        </Grid>
      </Grid>
      {isFetching &&
        <Grid container spacing={1} alignItems="center" sx={{ marginTop: 1 }}>
          <Grid item>
            <CircularProgress size={20} />
          </Grid>
          <Grid item xs>
            <Typography variant="body2" color="text.secondary">
              {t('import.link.loading')}
            </Typography>
          </Grid>
          <Grid item>
            <Button size="small" onClick={() => request('ytimportCancel')}>
              {t('import.cancel')}
            </Button>
          </Grid>
        </Grid>
      }
      {error &&
        <Alert severity="error" sx={{ marginTop: 1 }}>{error}</Alert>
      }
    </form>
  );
};

export default LinkForm;
