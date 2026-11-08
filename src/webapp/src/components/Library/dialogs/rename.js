import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Alert,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  InputAdornment,
  Stack,
  TextField,
  Typography,
} from '@mui/material';

import request from '../../../utils/request';
import { cleanName, renameErrorKey } from './utils';

// Rename a folder or song of the music library (path: absolute, as listed by the folder view).
// Songs: file name (without extension) and title tag. onRenamed gets the new absolute path.
const RenameDialog = ({ open, path, onClose, onRenamed }) => {
  const { t } = useTranslation();
  const [info, setInfo] = useState(undefined);
  const [name, setName] = useState('');
  const [title, setTitle] = useState('');
  const [error, setError] = useState(undefined);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!open) return;

    let isMounted = true;
    setInfo(undefined);
    setError(undefined);
    const fetchInfo = async () => {
      const { result, error } = await request('getRenameInfo', { path });
      if (!isMounted) return;
      if (error) return setError(renameErrorKey(error));
      setInfo(result);
      setName(result.name);
      setTitle(result.title || '');
    };

    fetchInfo();
    return () => { isMounted = false; };
  }, [open, path]);

  const isFile = info?.type === 'file';
  const cleanedName = cleanName(name);
  const isNameChanged = !!info && name !== info.name;
  const isTitleChanged = isFile && info.title_supported && title.trim() !== (info.title || '');
  const canSave = !!info && !!cleanedName && (isNameChanged || isTitleChanged) && !isSaving;

  const save = async (event) => {
    event.preventDefault();
    if (!canSave) return;

    setIsSaving(true);
    setError(undefined);
    const kwargs = { path, new_name: name };
    if (isTitleChanged) kwargs.title = title;
    const { result, error } = await request('renameLibraryEntry', kwargs);
    setIsSaving(false);

    if (error) return setError(renameErrorKey(error));
    onRenamed(result);
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <form onSubmit={save}>
        <DialogTitle>
          {t(isFile ? 'library.rename.title-song' : 'library.rename.title-folder')}
        </DialogTitle>
        <DialogContent>
          {!info && !error && <CircularProgress />}
          {info &&
            <Stack spacing={2} sx={{ paddingTop: 1 }}>
              <TextField
                autoFocus
                fullWidth
                label={t(isFile ? 'library.rename.file-name' : 'library.rename.folder-name')}
                value={name}
                onChange={(event) => setName(event.target.value)}
                error={!cleanedName}
                helperText={
                  !cleanedName
                    ? t('library.rename.errors.invalid-name')
                    : cleanedName !== name.trim() && t('library.rename.cleaned-name', { name: cleanedName })
                }
                InputProps={info.extension
                  ? { endAdornment: <InputAdornment position="end">{info.extension}</InputAdornment> }
                  : undefined
                }
              />
              {isFile &&
                <TextField
                  fullWidth
                  label={t('library.rename.song-title')}
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  disabled={!info.title_supported}
                  helperText={!info.title_supported && t('library.rename.title-not-supported')}
                />
              }
              {info.cards > 0 &&
                <Typography variant="body2" color="textSecondary">
                  {t('library.rename.cards', { count: info.cards })}
                </Typography>
              }
            </Stack>
          }
          {error && <Alert severity="error" sx={{ marginTop: 2 }}>{t(error)}</Alert>}
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>
            {t('general.buttons.cancel')}
          </Button>
          <Button type="submit" color="primary" disabled={!canSave}>
            {t('general.buttons.save')}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default RenameDialog;
