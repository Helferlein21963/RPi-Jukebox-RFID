import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  List,
  ListItem,
  Stack,
  Typography,
  useMediaQuery,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';

import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import AudioFileOutlinedIcon from '@mui/icons-material/AudioFileOutlined';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';

import request from '../../../utils/request';
import useDragSort from '../../../utils/use-drag-sort';
import { compareRecent, compareText } from '../sort';
import { reorderErrorKey, reorderNames, stripNumber, trackNumber } from './utils';

const titleOf = (song) => stripNumber(song.file.replace(/\.[^.]+$/, ''));
const numberOf = (song) => song.track ?? trackNumber(song.file) ?? Infinity;

// Orders the songs can be put into at once; afterwards single songs can still be moved
const SORTERS = {
  'name-asc': (a, b) => compareText(titleOf(a), titleOf(b)),
  'name-desc': (a, b) => compareText(titleOf(b), titleOf(a)),
  track: (a, b) => (numberOf(a) - numberOf(b)) || compareText(titleOf(a), titleOf(b)),
  newest: (a, b) => compareRecent(a.modified, b.modified) || compareText(titleOf(a), titleOf(b)),
  oldest: (a, b) => compareRecent(b.modified, a.modified) || compareText(titleOf(a), titleOf(b)),
};

const move = (list, from, to) => {
  const result = [...list];
  const [item] = result.splice(from, 1);
  result.splice(to, 0, item);
  return result;
};

// Change the order of a folder (path: absolute, as listed by the folder view).
// Saving renames its songs to '01 - …', '02 - …', as the folder is played in the order of the file names.
const ReorderDialog = ({ open, folder, onClose, onSaved }) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'));
  const [songs, setSongs] = useState(undefined);
  const [error, setError] = useState(undefined);
  const [isSaving, setIsSaving] = useState(false);
  // Songs can also be dragged at their handle; the content scrolls near its edges
  const contentRef = useRef(null);
  const { rowRef, handleProps, draggingKey } = useDragSort({
    items: songs || [],
    setItems: setSongs,
    getKey: (song) => song.file,
    scrollRef: contentRef,
  });

  useEffect(() => {
    if (!open) return;

    let isMounted = true;
    setSongs(undefined);
    setError(undefined);
    const fetchSongs = async () => {
      const { result, error } = await request('getOrderInfo', { folder });
      if (!isMounted) return;
      if (error) return setError(reorderErrorKey(error));
      setSongs(result);
    };

    fetchSongs();
    return () => { isMounted = false; };
  }, [open, folder]);

  const names = songs ? reorderNames(songs.map((song) => song.file)) : [];
  // Nothing to do when every song has its new name already
  const isChanged = !!songs && songs.some((song, idx) => song.file !== names[idx]);

  const save = async () => {
    setIsSaving(true);
    setError(undefined);
    const { error } = await request('reorderFolder', { folder, files: songs.map((song) => song.file) });
    setIsSaving(false);

    if (error) return setError(reorderErrorKey(error));
    onSaved();
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm" fullScreen={fullScreen}>
      <DialogTitle sx={{ overflowWrap: 'anywhere' }}>
        {t('library.reorder.title', { folder: folder.split('/').pop() })}
      </DialogTitle>
      <DialogContent ref={contentRef}>
        {!songs && !error && <CircularProgress />}
        {songs &&
          <Stack spacing={1}>
            <Box>
              <Typography variant="subtitle2" component="span" sx={{ marginRight: 1 }}>
                {t('library.reorder.sort-by')}
              </Typography>
              {Object.keys(SORTERS).map((sort) => (
                <Button
                  key={sort}
                  size="small"
                  onClick={() => setSongs([...songs].sort(SORTERS[sort]))}
                >
                  {t(`library.reorder.sort.${sort}`)}
                </Button>
              ))}
            </Box>
            <List dense disablePadding>
              {songs.map((song, idx) => (
                <ListItem
                  key={song.file}
                  ref={rowRef(song.file)}
                  disableGutters
                  // The dragged song floats above the others
                  sx={draggingKey === song.file
                    ? { position: 'relative', zIndex: 1, backgroundColor: 'grey.800', boxShadow: 8 }
                    : undefined
                  }
                >
                  <Box
                    {...handleProps(song.file)}
                    aria-label={t('library.reorder.drag')}
                    title={t('library.reorder.drag')}
                    sx={{ display: 'flex', alignItems: 'center', alignSelf: 'stretch', paddingX: 0.5, marginLeft: -0.5 }}
                  >
                    <DragIndicatorIcon color="action" />
                  </Box>
                  <AudioFileOutlinedIcon color="action" sx={{ marginX: 1, flexShrink: 0 }} />
                  <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                    <Typography variant="body1" sx={{ overflowWrap: 'anywhere' }}>
                      {song.file}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ overflowWrap: 'anywhere' }}>
                      {names[idx] === song.file
                        ? t('library.reorder.unchanged')
                        : t('library.reorder.becomes', { name: names[idx] })}
                    </Typography>
                  </Box>
                  <IconButton
                    size="small"
                    aria-label={t('library.reorder.move-up')}
                    disabled={idx === 0}
                    onClick={() => setSongs(move(songs, idx, idx - 1))}
                  >
                    <ArrowUpwardIcon fontSize="small" />
                  </IconButton>
                  <IconButton
                    size="small"
                    edge="end"
                    aria-label={t('library.reorder.move-down')}
                    disabled={idx === songs.length - 1}
                    onClick={() => setSongs(move(songs, idx, idx + 1))}
                  >
                    <ArrowDownwardIcon fontSize="small" />
                  </IconButton>
                </ListItem>
              ))}
            </List>
            <Alert severity="info">{t('library.reorder.hint')}</Alert>
          </Stack>
        }
        {error && <Alert severity="error" sx={{ marginTop: 2 }}>{t(error)}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>
          {t('general.buttons.cancel')}
        </Button>
        <Button color="primary" disabled={!isChanged || isSaving} onClick={save}>
          {t('general.buttons.save')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ReorderDialog;
