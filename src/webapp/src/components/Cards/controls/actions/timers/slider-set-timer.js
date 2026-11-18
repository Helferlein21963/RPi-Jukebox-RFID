import React, { useEffect } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Grid,
  Typography,
} from '@mui/material';

import {
  getActionAndCommand,
  getArgsValues,
} from '../../../utils';
import { SliderTimer } from '../../../../general';

// Wait time of a new timer card [s]
const DEFAULT_WAIT_SECONDS = 60 * 60;

const SliderSetTimer = ({
  actionData,
  handleActionDataChange,
}) => {
  const { t } = useTranslation();

  const { action, command } = getActionAndCommand(actionData);
  const [wait_seconds] = getArgsValues(actionData);
  const valid = Number(wait_seconds) > 0;

  // Always save a wait time: without one (or with 0 = off from older versions)
  // the card would start the timer with the core's default or at once
  useEffect(() => {
    if (!valid) {
      handleActionDataChange(action, command, { wait_seconds: DEFAULT_WAIT_SECONDS });
    }
  }, [valid, action, command, handleActionDataChange]);

  const onChangeCommitted = (event, wait_seconds) => {
    handleActionDataChange(action, command, { wait_seconds })
  };

  return (
    <Grid container alignItems="center" sx={{ marginTop: '20px' }}>
      <Grid item xs={12}>
        <Typography>
          {t('cards.controls.actions.timers.description')}
        </Typography>
        <SliderTimer
          value={valid ? wait_seconds : DEFAULT_WAIT_SECONDS}
          onChangeCommitted={onChangeCommitted}
        />
      </Grid>
    </Grid>
  );
};

export default SliderSetTimer;
