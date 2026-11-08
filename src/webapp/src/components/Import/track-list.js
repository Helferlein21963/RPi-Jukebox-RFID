import React from 'react';
import { useTranslation } from 'react-i18next';

import {
  Button,
  Checkbox,
  Grid,
  IconButton,
  List,
  ListItem,
  TextField,
  Typography,
} from '@mui/material';

import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';

import { toHHMMSS } from '../../utils/utils';
import { formatDate, moveItem } from './utils';

const TrackList = ({ tracks, setTracks }) => {
  const { t, i18n } = useTranslation();
  const selectedCount = tracks.filter((track) => track.selected).length;

  // Date (podcast episodes) and duration below the title
  const details = (track) => (
    [formatDate(track.date, i18n?.language), track.duration ? toHHMMSS(track.duration) : null]
      .filter(Boolean)
      .join(' · ') || ' '
  );

  const updateTrack = (idx, values) => setTracks(
    tracks.map((track, i) => (i === idx ? { ...track, ...values } : track))
  );

  const selectAll = (selected) => setTracks(
    tracks.map((track) => ({ ...track, selected: selected && track.available }))
  );

  return (
    <>
      <Grid container alignItems="center">
        <Grid item xs>
          <Typography variant="subtitle2">
            {t('import.editor.tracks', { selected: selectedCount, total: tracks.length })}
          </Typography>
        </Grid>
        <Grid item>
          <Button size="small" onClick={() => selectAll(true)}>
            {t('import.editor.select-all')}
          </Button>
          <Button size="small" onClick={() => selectAll(false)}>
            {t('import.editor.select-none')}
          </Button>
          {tracks.length > 1 &&
            <Button size="small" onClick={() => setTracks([...tracks].reverse())}>
              {t('import.editor.reverse')}
            </Button>
          }
        </Grid>
      </Grid>
      <List dense disablePadding>
        {tracks.map((track, idx) => (
          <ListItem
            key={track.key}
            disableGutters
            sx={{ alignItems: 'center', opacity: track.selected ? 1 : 0.5 }}
          >
            <Checkbox
              edge="start"
              size="small"
              checked={track.selected}
              disabled={!track.available}
              onChange={(event) => updateTrack(idx, { selected: event.target.checked })}
              inputProps={{ 'aria-label': track.title }}
            />
            <TextField
              fullWidth
              size="small"
              variant="standard"
              value={track.title}
              disabled={!track.available}
              onChange={(event) => updateTrack(idx, { title: event.target.value })}
              helperText={track.available ? details(track) : t('import.editor.unavailable')}
            />
            <IconButton
              size="small"
              aria-label={t('import.editor.move-up')}
              disabled={idx === 0}
              onClick={() => setTracks(moveItem(tracks, idx, idx - 1))}
            >
              <ArrowUpwardIcon fontSize="small" />
            </IconButton>
            <IconButton
              size="small"
              edge="end"
              aria-label={t('import.editor.move-down')}
              disabled={idx === tracks.length - 1}
              onClick={() => setTracks(moveItem(tracks, idx, idx + 1))}
            >
              <ArrowDownwardIcon fontSize="small" />
            </IconButton>
          </ListItem>
        ))}
      </List>
    </>
  );
};

export default TrackList;
