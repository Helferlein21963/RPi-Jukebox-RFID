import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Divider,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import TimerOutlinedIcon from '@mui/icons-material/TimerOutlined';

import { TIMER_STEPS } from '../../../config';
import ActiveTimer from './active-timer';
import CustomTime from './custom-time';
import TimerIcon from './timer-icon';
import useNow from '../../../utils/use-now';
import { TIMER_TYPES, useTimers } from './use-timers';
import { defaultClock, durationSeconds, parseTime, secondsUntil } from './utils';

const DURATIONS = TIMER_STEPS.filter((minutes) => minutes > 0);
const CUSTOM = 'custom';
const CUSTOM_MODES = ['duration', 'clock'];

const STORAGE_KEY_TYPE = 'timerLastType';
const STORAGE_KEY_MINUTES = 'timerLastMinutes';
const STORAGE_KEY_CUSTOM_MODE = 'timerCustomMode';
const STORAGE_KEY_CUSTOM_DURATION = 'timerCustomDuration';
const STORAGE_KEY_CUSTOM_CLOCK = 'timerCustomClock';
const STORAGE_KEY_FADE_SECONDS = 'timerFadeSeconds';

const DEFAULT_TYPE = 'fade-volume';
const DEFAULT_MINUTES = 30;
const DEFAULT_CUSTOM_DURATION = '00:45';
const DEFAULT_FADE_SECONDS = '10';

// Fade out duration: whole seconds, at least 1
const isFadeSeconds = (value) => /^\d+$/.test(value || '') && Number(value) >= 1;

const loadSetting = (key, isValid, fallback) => {
  try {
    const value = localStorage.getItem(key);
    return isValid(value) ? value : fallback;
  }
  catch {
    return fallback;
  }
};

const saveSetting = (key, value) => {
  try {
    localStorage.setItem(key, value);
  }
  catch {
    // Not available (private mode): the selection is just not remembered
  }
};

// State that is remembered in localStorage
const useSetting = (key, isValid, fallback) => {
  const [value, setValue] = useState(() => loadSetting(key, isValid, fallback));
  const update = (newValue) => {
    setValue(newValue);
    saveSetting(key, newValue);
  };
  return [value, update];
};

const isTime = (value) => parseTime(value) !== null;

// Chips with two lines (duration and end time), all of the same height
const chipSx = {
  height: 'auto',
  paddingY: 0.5,
  borderRadius: 2,
  '& .MuiChip-label': { textAlign: 'center', fontVariantNumeric: 'tabular-nums' },
};

const SectionLabel = ({ children }) => (
  <Typography variant="subtitle2" color="text.secondary" sx={{ marginBottom: 1 }}>
    {children}
  </Typography>
);

const SettingsTimers = () => {
  const { t, i18n } = useTranslation();
  const { timers, error, start, cancel, refreshAll } = useTimers();
  const now = useNow();

  const [type, setType] = useSetting(
    STORAGE_KEY_TYPE, (value) => TIMER_TYPES.includes(value), DEFAULT_TYPE
  );
  // A preset in minutes (as string) or 'custom'
  const [selection, setSelection] = useSetting(
    STORAGE_KEY_MINUTES,
    (value) => value === CUSTOM || DURATIONS.includes(Number(value)),
    String(DEFAULT_MINUTES)
  );
  const [customMode, setCustomMode] = useSetting(
    STORAGE_KEY_CUSTOM_MODE, (value) => CUSTOM_MODES.includes(value), 'duration'
  );
  const [customDuration, setCustomDuration] = useSetting(
    STORAGE_KEY_CUSTOM_DURATION, isTime, DEFAULT_CUSTOM_DURATION
  );
  const [customClock, setCustomClock] = useSetting(
    STORAGE_KEY_CUSTOM_CLOCK, isTime, defaultClock()
  );
  const [fadeSeconds, setFadeSeconds] = useSetting(
    STORAGE_KEY_FADE_SECONDS, isFadeSeconds, DEFAULT_FADE_SECONDS
  );
  const [isStarting, setIsStarting] = useState(false);

  const activeTypes = TIMER_TYPES.filter((type) => timers[type]?.enabled);
  const isRestart = activeTypes.includes(type);
  const isCustom = selection === CUSTOM;

  // Seconds until the timer would end when started now
  const seconds = !isCustom
    ? Number(selection) * 60
    : customMode === 'clock'
      ? secondsUntil(customClock, new Date(now))
      : durationSeconds(customDuration);
  const isFade = type === 'fade-volume';
  const isFadeValid = isFadeSeconds(fadeSeconds);
  const isValid = seconds > 0 && (!isFade || isFadeValid);

  const formatDuration = (minutes) => {
    if (minutes < 60) return t('settings.timers.duration-minutes', { value: minutes });
    const hours = Math.floor(minutes / 60);
    const rest = minutes % 60;
    const value = rest ? `${hours}:${String(rest).padStart(2, '0')}` : hours;
    return t('settings.timers.duration-hours', { value });
  };

  const formatClock = (timestamp) => new Date(timestamp).toLocaleTimeString(
    i18n.language, { hour: '2-digit', minute: '2-digit' }
  );

  // Text for the start button and the custom time preview
  const startLabel = isCustom && customMode === 'clock'
    ? t('settings.timers.until', { time: customClock.slice(0, 5) })
    : formatDuration(Math.ceil(seconds / 60));
  const customPreview = customMode === 'clock'
    ? t('settings.timers.in', { duration: formatDuration(Math.max(1, Math.ceil(seconds / 60))) })
    : t('settings.timers.ends-at', { time: formatClock(now + seconds * 1000) });

  // Fade out duration for the hint: a fade longer than the timer takes the whole time
  const formatSeconds = (value) => {
    if (value < 60) return t('settings.timers.duration-seconds', { value });
    if (value % 60 === 0) return formatDuration(value / 60);
    const minutes = Math.floor(value / 60);
    const rest = String(Math.round(value % 60)).padStart(2, '0');
    return t('settings.timers.duration-minutes', { value: `${minutes}:${rest}` });
  };
  const fadeHintSeconds = seconds > 0 ? Math.min(Number(fadeSeconds), seconds) : Number(fadeSeconds);

  const handleType = (event, value) => {
    if (value) setType(value); // Keep one type selected
  };

  const handleStart = async () => {
    setIsStarting(true);
    // Recalculate: the end time of day must not use the value of the last render
    const startSeconds = isCustom && customMode === 'clock' ? secondsUntil(customClock) : seconds;
    await start(type, startSeconds, isFade ? { fade_seconds: Number(fadeSeconds) } : {});
    setIsStarting(false);
  };

  return (
    <Card>
      <CardHeader title={t('settings.timers.title')} />
      <Divider />
      <CardContent>
        <Stack spacing={2}>
          {activeTypes.length > 0
            ? activeTypes.map((activeType) => (
              <ActiveTimer
                key={activeType}
                type={activeType}
                timer={timers[activeType]}
                onCancel={() => cancel(activeType)}
                onExpired={refreshAll}
              />
            ))
            : (
              <Typography color="text.secondary">
                {t('settings.timers.none-active')}
              </Typography>
            )
          }
          {error &&
            <Alert severity="error">{t('settings.timers.error')}</Alert>
          }

          <Divider />

          <Box>
            <SectionLabel>{t('settings.timers.action')}</SectionLabel>
            <ToggleButtonGroup
              value={type}
              exclusive
              fullWidth
              onChange={handleType}
              color="primary"
            >
              {TIMER_TYPES.map((timerType) => (
                <ToggleButton
                  key={timerType}
                  value={timerType}
                  sx={{ flexDirection: 'column', gap: 0.5, textTransform: 'none', lineHeight: 1.2 }}
                >
                  <TimerIcon type={timerType} />
                  {t(`settings.timers.short-${timerType}`)}
                </ToggleButton>
              ))}
            </ToggleButtonGroup>
            {isFade &&
              <TextField
                id="timer-fade-seconds"
                type="number"
                label={t('settings.timers.fade-seconds-label')}
                value={fadeSeconds}
                onChange={(event) => setFadeSeconds(event.target.value)}
                InputLabelProps={{ shrink: true }}
                inputProps={{ min: 1, step: 1, inputMode: 'numeric' }}
                error={!isFadeValid}
                helperText={isFadeValid ? null : t('settings.timers.fade-seconds-invalid')}
                sx={{ marginTop: 2, width: 220 }}
              />
            }
            <Typography variant="body2" color="text.secondary" sx={{ marginTop: 1 }}>
              {isFade && !isFadeValid
                ? null
                : t(`settings.timers.hint-${type}`, { duration: formatSeconds(fadeHintSeconds) })}
            </Typography>
          </Box>

          <Box>
            <SectionLabel>{t('settings.timers.duration')}</SectionLabel>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {DURATIONS.map((value) => {
                const selected = String(value) === selection;
                return (
                  <Chip
                    key={value}
                    label={
                      <>
                        <Box component="span" sx={{ display: 'block' }}>
                          {formatDuration(value)}
                        </Box>
                        <Box component="span" sx={{ display: 'block', fontSize: '0.75rem', opacity: 0.8 }}>
                          {t('settings.timers.chip-until', { time: formatClock(now + value * 60 * 1000) })}
                        </Box>
                      </>
                    }
                    color={selected ? 'primary' : 'default'}
                    variant={selected ? 'filled' : 'outlined'}
                    onClick={() => setSelection(String(value))}
                    sx={chipSx}
                  />
                );
              })}
              <Chip
                sx={chipSx}
                icon={<EditIcon />}
                label={t('settings.timers.custom')}
                color={isCustom ? 'primary' : 'default'}
                variant={isCustom ? 'filled' : 'outlined'}
                onClick={() => setSelection(CUSTOM)}
              />
            </Box>
            {isCustom &&
              <CustomTime
                mode={customMode}
                onModeChange={setCustomMode}
                value={customMode === 'clock' ? customClock : customDuration}
                onValueChange={customMode === 'clock' ? setCustomClock : setCustomDuration}
                preview={customPreview}
                isValid={isValid}
                currentTime={formatClock(now)}
              />
            }
          </Box>

          <Button
            variant="contained"
            size="large"
            startIcon={<TimerOutlinedIcon />}
            onClick={handleStart}
            disabled={isStarting || !isValid}
          >
            {t(isRestart ? 'settings.timers.restart' : 'settings.timers.start', {
              duration: startLabel,
            })}
          </Button>
        </Stack>
      </CardContent>
    </Card>
  );
};

export default SettingsTimers;
