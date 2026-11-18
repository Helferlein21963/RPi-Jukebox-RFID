import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Slider } from '@mui/material';

import { TIMER_STEPS } from '../../config';

// The first step (0 = off) is left out: a card or timer started with 0 seconds would run at once
const MIN_STEP = 1;

/**
 * Slider over the TIMER_STEPS (minutes); reports seconds
 */
const SliderTimer = ({ onChangeCommitted, value }) => {
  const { t } = useTranslation();

  const marks = TIMER_STEPS
    .map((value, index) => ({ label: value, value: index }))
    .filter(({ value }) => value >= MIN_STEP);

  const valueLabelFormat = (value) => {
    if (value === 0) return t('settings.timers.option-label-off');
    return t('settings.timers.option-label-timeslot', { value });
  }

  const getStepFromSeconds = (seconds) => (
    Math.max(MIN_STEP, TIMER_STEPS.indexOf(seconds / 60))
  );

  const [step, setStep] = useState(
    getStepFromSeconds(value)
  );
  // Follow a value set from outside (e.g. the default for a new card)
  useEffect(() => setStep(getStepFromSeconds(value)), [value]);
  const handleChange = (event, step) => setStep(step);

  const handleOnChangeCommitted = (event, value) => (
    onChangeCommitted(event, TIMER_STEPS[value] * 60)
  );

  return (
    <Slider
      value={step}
      marks={marks}
      max={TIMER_STEPS.length-1}
      getAriaValueText={valueLabelFormat}
      valueLabelFormat={valueLabelFormat}
      min={MIN_STEP}
      step={1}
      scale={(value) => TIMER_STEPS[value]}
      valueLabelDisplay="auto"
      onChange={handleChange}
      onChangeCommitted={handleOnChangeCommitted}
    />
  );
};

export default SliderTimer;
