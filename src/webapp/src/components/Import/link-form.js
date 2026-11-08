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
  // Feedback right after the click: the state 'fetching' only arrives with the next published status
  const [isSending, setIsSending] = useState(false);
  const isFetching = status?.state === 'fetching';
  const isLoading = isSending || isFetching;

  // Show the link of a job that was started elsewhere (other device, page reload)
  useEffect(() => {
    if (status?.url) setUrl(status.url);
  }, [status?.url]);

  // Any new state of the core ends the waiting; the timer in case no status arrives
  useEffect(() => {
    setIsSending(false);
  }, [status?.state]);

  useEffect(() => {
    if (!isSending) return undefined;
    const timer = setTimeout(() => setIsSending(false), 10000);
    return () => clearTimeout(timer);
  }, [isSending]);

  const fetchInfo = async (event) => {
    event.preventDefault();
    if (isLoading) return;
    setError(null);
    setIsSending(true);
    const { error } = await request('ytimportFetchInfo', { url: url.trim() });
    if (error) {
      setIsSending(false);
      setError(String(error));
    }
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
            disabled={disabled || isSending}
            onChange={(event) => setUrl(event.target.value)}
          />
        </Grid>
        <Grid item>
          <Button
            type="submit"
            variant="contained"
            disabled={disabled || isSending || !url.trim()}
          >
            {t('import.link.load')}
          </Button>
        </Grid>
      </Grid>
      {isLoading &&
        <Grid container spacing={1} alignItems="center" sx={{ marginTop: 1 }}>
          <Grid item>
            <CircularProgress size={20} />
          </Grid>
          <Grid item xs>
            <Typography variant="body2" color="text.secondary">
              {t('import.link.loading')}
            </Typography>
          </Grid>
          {isFetching &&
            <Grid item>
              <Button size="small" onClick={() => request('ytimportCancel')}>
                {t('import.cancel')}
              </Button>
            </Grid>
          }
        </Grid>
      }
      {error &&
        <Alert severity="error" sx={{ marginTop: 1 }}>{error}</Alert>
      }
    </form>
  );
};

export default LinkForm;
