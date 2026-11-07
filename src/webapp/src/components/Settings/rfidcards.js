import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Card,
  CardContent,
  CardHeader,
  Divider,
  FormControlLabel,
  FormGroup,
  Grid,
  Radio,
  RadioGroup,
  Slider,
  Typography,
} from '@mui/material';

import { useTheme } from '@mui/material/styles';

import { SwitchWithLoader } from '../general';

import request from '../../utils/request';

// Values of playermpd.second_swipe_action
const secondSwipeActions = ['toggle', 'rewind', 'skip', 'ignore'];

const delayMarks = [1, 2, 3, 4, 5].map(
  (value) => ({ value, label: `${value} s` })
);

const Description = ({ children }) => (
  <Typography variant="body2" color="text.secondary">
    {children}
  </Typography>
);

const SettingsRfidCards = () => {
  const { t } = useTranslation();
  const theme = useTheme();

  const [secondSwipeAction, setSecondSwipeAction] = useState('');
  const [resume, setResume] = useState(false);
  const [isResumeLoading, setIsResumeLoading] = useState(true);
  const [sameIdDelay, setSameIdDelay] = useState(2);

  useEffect(() => {
    const fetchSettings = async () => {
      const [swipe, resumeState, delay] = await Promise.all([
        request('getSecondSwipeAction'),
        request('getPlayCardResume'),
        request('getSameIdDelay'),
      ]);
      if (swipe.result !== undefined) setSecondSwipeAction(swipe.result);
      if (resumeState.result !== undefined) setResume(resumeState.result);
      if (delay.result !== undefined) setSameIdDelay(delay.result);
      setIsResumeLoading(false);
    };

    fetchSettings();
  }, []);

  const handleSecondSwipeChange = async (event) => {
    const action = event.target.value;
    const previous = secondSwipeAction;
    setSecondSwipeAction(action);
    const { error } = await request('setSecondSwipeAction', { action });
    if (error) setSecondSwipeAction(previous);
  };

  const toggleResume = async () => {
    const enabled = !resume;
    setIsResumeLoading(true);
    setResume(enabled);
    const { error } = await request('setPlayCardResume', { enabled });
    if (error) setResume(!enabled);
    setIsResumeLoading(false);
  };

  const updateSameIdDelay = async (event, delay) => {
    const { error } = await request('setSameIdDelay', { delay });
    if (error) {
      const { result } = await request('getSameIdDelay');
      if (result !== undefined) setSameIdDelay(result);
    }
  };

  return (
    <Card>
      <CardHeader title={t('settings.rfidcards.title')} />
      <Divider />
      <CardContent>
        <Typography>{t('settings.rfidcards.second-swipe.title')}</Typography>
        <Description>{t('settings.rfidcards.second-swipe.description')}</Description>
        <RadioGroup
          aria-label={t('settings.rfidcards.second-swipe.title')}
          name="second-swipe-action"
          value={secondSwipeAction}
          onChange={handleSecondSwipeChange}
        >
          {secondSwipeActions.map((action) => (
            <FormControlLabel
              key={action}
              value={action}
              control={<Radio />}
              label={t(`settings.rfidcards.second-swipe.${action}`)}
            />
          ))}
        </RadioGroup>
      </CardContent>
      <Divider />
      <CardContent>
        <FormGroup>
          <FormControlLabel
            sx={{
              justifyContent: 'space-between',
              marginLeft: '0',
            }}
            control={
              <SwitchWithLoader
                isLoading={isResumeLoading}
                checked={resume}
                onChange={toggleResume}
              />
            }
            label={t('settings.rfidcards.resume.title')}
            labelPlacement="start"
          />
        </FormGroup>
        <Description>{t('settings.rfidcards.resume.description')}</Description>
      </CardContent>
      <Divider />
      <CardContent>
        <Grid container direction="column">
          <Typography>{t('settings.rfidcards.same-id-delay.title')}</Typography>
          <Description>{t('settings.rfidcards.same-id-delay.description')}</Description>
          <Grid item sx={{ padding: theme.spacing(1) }}>
            <Slider
              aria-label={t('settings.rfidcards.same-id-delay.title')}
              value={typeof sameIdDelay === 'number' ? sameIdDelay : 2}
              onChange={(event, value) => setSameIdDelay(value)}
              onChangeCommitted={updateSameIdDelay}
              marks={delayMarks}
              min={0.5}
              max={5}
              step={0.5}
              valueLabelDisplay="auto"
              valueLabelFormat={(value) => `${value} s`}
            />
          </Grid>
          <Description>{t('settings.rfidcards.same-id-delay.hint')}</Description>
        </Grid>
      </CardContent>
    </Card>
  );
};

export default SettingsRfidCards;
