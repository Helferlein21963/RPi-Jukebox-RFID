import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Alert,
  Button,
  CircularProgress,
  Grid,
  Typography,
} from '@mui/material';

import request from '../../utils/request';
import { isBusy } from './utils';

const Tools = ({ status }) => {
  const { t } = useTranslation();
  const [versions, setVersions] = useState(null);
  const [error, setError] = useState(null);
  const state = status?.state;

  // Load again after an installation / update
  useEffect(() => {
    if (state === 'updating') return;
    const fetchVersions = async () => {
      const { result } = await request('ytimportGetVersions');
      if (result) setVersions(result);
    };
    fetchVersions();
  }, [state]);

  const update = async () => {
    setError(null);
    const { error } = await request('ytimportUpdate');
    if (error) setError(String(error));
  };

  if (!versions) return null;

  const {
    ytdlp,
    restart_required: restartRequired,
    ffmpeg,
    js_runtime: jsRuntime,
    js_runtime_version: jsVersion,
    js_runtime_supported: jsSupported,
    js_runtime_min: jsMin,
  } = versions;
  const isInstalled = !!ytdlp && !!versions.mutagen;

  return (
    <Grid container direction="column" spacing={1}>
      <Grid item>
        <Grid container alignItems="center" spacing={1}>
          <Grid item xs>
            <Typography variant="body2" color="text.secondary">
              {isInstalled
                ? t('import.tools.versions', { ytdlp, runtime: jsRuntime, version: jsVersion || '-' })
                : t('import.tools.ytdlp-missing')
              }
            </Typography>
          </Grid>
          <Grid item>
            {state === 'updating'
              ? <CircularProgress size={20} />
              : <Button size="small" disabled={isBusy(status)} onClick={update}>
                  {isInstalled ? t('import.tools.update') : t('import.tools.install')}
                </Button>
            }
          </Grid>
        </Grid>
      </Grid>
      {state === 'updating' &&
        <Grid item>
          <Alert severity="info">{t('import.tools.updating')}</Alert>
        </Grid>
      }
      {state === 'updated' &&
        <Grid item>
          <Alert severity="success">{t('import.tools.updated', { version: ytdlp })}</Alert>
        </Grid>
      }
      {restartRequired &&
        <Grid item>
          <Alert
            severity="warning"
            action={
              <Button color="inherit" size="small" onClick={() => request('restartService')}>
                {t('import.tools.restart')}
              </Button>
            }
          >
            {t('import.tools.restart-required')}
          </Alert>
        </Grid>
      }
      {!ffmpeg &&
        <Grid item>
          <Alert severity="error">{t('import.tools.ffmpeg-missing')}</Alert>
        </Grid>
      }
      {isInstalled && !jsVersion &&
        <Grid item>
          <Alert severity="warning">{t('import.tools.js-missing', { runtime: jsRuntime })}</Alert>
        </Grid>
      }
      {isInstalled && jsVersion && jsSupported === false &&
        <Grid item>
          <Alert severity="warning">
            {t('import.tools.js-old', { runtime: jsRuntime, version: jsVersion, min: jsMin })}
          </Alert>
        </Grid>
      }
      {error &&
        <Grid item>
          <Alert severity="error">{error}</Alert>
        </Grid>
      }
    </Grid>
  );
};

export default Tools;
