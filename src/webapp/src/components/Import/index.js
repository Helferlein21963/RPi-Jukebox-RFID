import React, { useContext, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Card,
  CardContent,
  CardHeader,
  Divider,
  Grid,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';

import PubSubContext from '../../context/pubsub/context';
import request from '../../utils/request';
import Editor from './editor';
import LinkForm from './link-form';
import ImportProgress from './progress';
import Result from './result';
import Tools from './tools';
import { isBusy } from './utils';

// Import audio from YouTube (core plugin 'ytimport'): link -> edit titles -> download & convert on the box
const Import = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const { state: { 'ytimport.status': publishedStatus } } = useContext(PubSubContext);
  const [initialStatus, setInitialStatus] = useState(undefined);

  // The published status arrives with the next change; ask once to show a running job right away
  useEffect(() => {
    const fetchStatus = async () => {
      const { result } = await request('ytimportGetStatus');
      if (result) setInitialStatus(result);
    };
    fetchStatus();
  }, []);

  const status = publishedStatus || initialStatus || { state: 'idle' };
  const { state } = status;

  return (
    <Grid
      container
      direction="column"
      wrap="nowrap"
      id="import"
      sx={{
        '& > .MuiGrid-item': { marginBottom: theme.spacing(1) },
        // Long titles and folder names (no spaces, only '_') must not widen the page
        '& .MuiTypography-root, & .MuiFormHelperText-root, & .MuiAlert-message': { overflowWrap: 'anywhere' },
        padding: '10px',
      }}
    >
      <Grid item>
        <Card>
          <CardHeader title={t('import.title')} />
          <Divider />
          <CardContent>
            <Grid container direction="column" wrap="nowrap" spacing={2}>
              {state !== 'importing' &&
                <Grid item>
                  <LinkForm status={status} disabled={isBusy(status)} />
                </Grid>
              }
              {state === 'info' && status.info &&
                <Grid item>
                  <Editor key={status.info.url} info={status.info} />
                </Grid>
              }
              {state === 'importing' &&
                <Grid item>
                  <ImportProgress status={status} />
                </Grid>
              }
              {['done', 'cancelled', 'error'].includes(state) &&
                <Grid item>
                  <Result status={status} />
                </Grid>
              }
            </Grid>
          </CardContent>
        </Card>
      </Grid>
      <Grid item>
        <Card>
          <CardContent>
            <Tools status={status} />
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );
};

export default Import;
