import React from 'react';
import { useTranslation } from 'react-i18next';

import {
  Box,
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
import AudioFileOutlinedIcon from '@mui/icons-material/AudioFileOutlined';

import { toHHMMSS } from '../../utils/utils';
import { formatDate, moveItem, reorderNames } from './utils';

// Checkbox and file icon share this column, so that all titles start at the same position
const LEAD_WIDTH = 40;

// With 'reorder' (order of the whole existing folder) the files of the folder ('existing') are in the list:
// they can be moved, but not unselected or renamed. Every row shows its file name after the import.
const TrackList = ({ tracks, setTracks, reorder = false }) => {
  const { t, i18n } = useTranslation();
  const importable = tracks.filter((track) => !track.existing);
  const selectedCount = importable.filter((track) => track.selected).length;
  const names = reorder ? reorderNames(tracks) : {};

  // Below the title: existing/new, date (podcast episodes), duration and the new file name
  const details = (track) => {
    if (!track.existing && !track.available) return t('import.editor.unavailable');
    const parts = [];
    if (reorder) parts.push(track.existing ? t('import.editor.existing') : t('import.editor.new'));
    if (!track.existing) {
      parts.push(formatDate(track.date, i18n?.language));
      if (track.duration) parts.push(toHHMMSS(track.duration));
    }
    const text = parts.filter(Boolean).join(' · ');
    if (!reorder) return text || ' ';
    const name = names[track.key];
    const target = name ? t('import.editor.becomes', { name }) : t('import.editor.skipped');
    return `${text} ${target}`;
  };

  const updateTrack = (idx, values) => setTracks(
    tracks.map((track, i) => (i === idx ? { ...track, ...values } : track))
  );

  const selectAll = (selected) => setTracks(
    tracks.map((track) => (track.existing ? track : { ...track, selected: selected && track.available }))
  );

  const heading = reorder
    ? t('import.editor.tracks-reorder', {
      existing: tracks.length - importable.length,
      selected: selectedCount,
      total: importable.length,
    })
    : t('import.editor.tracks', { selected: selectedCount, total: importable.length });

  return (
    <>
      <Grid container alignItems="center">
        <Grid item xs>
          <Typography variant="subtitle2">{heading}</Typography>
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
            sx={{ alignItems: 'center', opacity: track.existing || track.selected ? 1 : 0.5 }}
          >
            <Box sx={{ width: LEAD_WIDTH, flexShrink: 0, display: 'flex', justifyContent: 'center' }}>
              {track.existing
                ? <AudioFileOutlinedIcon color="action" titleAccess={t('import.editor.existing')} />
                : <Checkbox
                    size="small"
                    checked={track.selected}
                    disabled={!track.available}
                    onChange={(event) => updateTrack(idx, { selected: event.target.checked })}
                    inputProps={{ 'aria-label': track.title }}
                  />
              }
            </Box>
            {track.existing
              // A file of the folder: its name as it is, not editable
              ? <Box sx={{ flexGrow: 1, minWidth: 0, paddingY: 0.5 }}>
                  <Typography variant="body1" sx={{ overflowWrap: 'anywhere' }}>{track.file}</Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ overflowWrap: 'anywhere' }}>
                    {details(track)}
                  </Typography>
                </Box>
              : <TextField
                  fullWidth
                  size="small"
                  variant="standard"
                  value={track.title}
                  disabled={!track.available}
                  onChange={(event) => updateTrack(idx, { title: event.target.value })}
                  helperText={details(track)}
                  FormHelperTextProps={{ sx: { overflowWrap: 'anywhere' } }}
                />
            }
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
