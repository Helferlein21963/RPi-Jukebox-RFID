import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import {
  Alert,
  Button,
  Grid,
} from '@mui/material';

import request from '../../utils/request';
import { buildActionData } from '../Cards/utils';
import { useMusicLibraryPath } from '../Library/now-playing';
import FailedTracks from './failed-tracks';

const Buttons = ({ children }) => (
  <Grid item>
    <Grid container spacing={1} justifyContent="flex-end">
      {React.Children.map(children, (child) => child && <Grid item>{child}</Grid>)}
    </Grid>
  </Grid>
);

const Result = ({ status }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { state, folder, imported, total, failed = [], error } = status;
  // The library works with absolute folder paths (as returned by the core)
  const libraryPath = useMusicLibraryPath();
  const folderPath = libraryPath ? `${libraryPath}/${folder}` : folder;

  const reset = () => request('ytimportReset');

  // Same as 'Assign card' in the library: play the folder
  const assignCard = () => {
    const actionData = buildActionData('play_music', 'play_folder', { folder: folderPath, recursive: true });
    navigate('/cards/register', { state: { registerCard: { actionData } } });
  };

  if (state === 'done') {
    return (
      <Grid container direction="column" wrap="nowrap" spacing={2}>
        <Grid item>
          <Alert severity="success">
            {t('import.result.done', { imported, total, folder })}
          </Alert>
        </Grid>
        {failed.length > 0 &&
          <Grid item>
            <FailedTracks failed={failed} />
          </Grid>
        }
        <Buttons>
          <Button onClick={reset}>{t('import.result.new-import')}</Button>
          <Button onClick={() => navigate(`/library/folders/${encodeURIComponent(folderPath)}`)}>
            {t('import.result.open-library')}
          </Button>
          <Button variant="contained" onClick={assignCard}>
            {t('import.result.assign-card')}
          </Button>
        </Buttons>
      </Grid>
    );
  }

  return (
    <Grid container direction="column" wrap="nowrap" spacing={2}>
      <Grid item>
        {state === 'cancelled'
          ? <Alert severity="info">{t('import.result.cancelled')}</Alert>
          : <Alert severity="error" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {t('import.result.error', { error })}
            </Alert>
        }
      </Grid>
      <Buttons>
        <Button onClick={reset}>{t('import.result.back')}</Button>
      </Buttons>
    </Grid>
  );
};

export default Result;
