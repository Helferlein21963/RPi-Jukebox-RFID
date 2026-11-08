import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Alert,
  Avatar,
  Button,
  FormControlLabel,
  Grid,
  Switch,
  TextField,
  Typography,
} from '@mui/material';

import request from '../../utils/request';
import FolderField from './folder-field';
import TrackList from './track-list';
import {
  buildTracks,
  chaptersOf,
  mergeTracks,
  newTracks,
  toImportTracks,
} from './utils';

// Below the folder field: new folder, or what happens in the existing folder
const folderHelp = (t, folderInfo, reorder) => {
  if (!folderInfo.exists) return t('import.editor.folder-new', { folder: folderInfo.folder });
  const count = folderInfo.tracks?.length || 0;
  if (reorder) return t('import.editor.folder-existing-reorder', { count });
  return folderInfo.numbered
    ? t('import.editor.folder-existing-append', { count })
    : t('import.editor.folder-existing-sorted', { count });
};

const Editor = ({ info, targetFolder }) => {
  const { t } = useTranslation();

  const chapterCount = chaptersOf(info).length;
  const hasChapters = chapterCount > 1;

  const [folder, setFolder] = useState(targetFolder || info.title || info.folder);
  // Answer of the core for the folder name, null until it is there
  const [folderInfo, setFolderInfo] = useState(null);
  const [artist, setArtist] = useState(info.uploader || '');
  const [album, setAlbum] = useState(info.title || '');
  const [splitChapters, setSplitChapters] = useState(hasChapters);
  const [cover, setCover] = useState(true);
  const [reorder, setReorder] = useState(false);
  const [tracks, setTracks] = useState(buildTracks(info, hasChapters));
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState(null);

  // The folder as the core will use it: a new one (name cleaned) or an existing one with its files
  useEffect(() => {
    let isCurrent = true;
    const timer = setTimeout(async () => {
      const { result } = await request('ytimportFolderInfo', { name: folder });
      if (isCurrent && result) setFolderInfo(result);
    }, 400);
    return () => {
      isCurrent = false;
      clearTimeout(timer);
    };
  }, [folder]);

  const exists = !!folderInfo?.exists;

  // Adding to an existing folder: keep its artist and album
  useEffect(() => {
    if (!exists) {
      setReorder(false);
      return;
    }
    if (folderInfo.artist) setArtist(folderInfo.artist);
    if (folderInfo.album) setAlbum(folderInfo.album);
  }, [exists, folderInfo?.folder]); // eslint-disable-line react-hooks/exhaustive-deps

  // The order of the whole folder: its files join the list of tracks
  useEffect(() => {
    setTracks((current) => (
      reorder && exists ? mergeTracks(folderInfo.tracks, current) : newTracks(current)
    ));
  }, [reorder, exists, folderInfo]);

  const toggleChapters = (event) => {
    setSplitChapters(event.target.checked);
    const rebuilt = buildTracks(info, event.target.checked);
    setTracks(reorder && exists ? mergeTracks(folderInfo.tracks, rebuilt) : rebuilt);
  };

  const isReorder = reorder && exists;
  const importTracks = toImportTracks(tracks, isReorder);
  const newCount = toImportTracks(tracks).length;
  const folderError = folderInfo && !folderInfo.folder ? t('import.editor.folder-empty') : null;

  const startImport = async () => {
    setIsStarting(true);
    setError(null);
    const { error } = await request('ytimportStart', {
      folder: exists ? folderInfo.folder : folder,
      tracks: importTracks,
      artist,
      album,
      cover,
      target: exists ? 'existing' : 'new',
      reorder: isReorder,
    });
    // On success, the status changes to 'importing' and this editor disappears
    if (error) {
      setError(String(error));
      setIsStarting(false);
    }
  };

  return (
    <Grid container direction="column" wrap="nowrap" spacing={2}>
      <Grid item>
        <Grid container spacing={2} alignItems="center" wrap="nowrap">
          {info.thumbnail &&
            <Grid item>
              <Avatar
                variant="rounded"
                src={info.thumbnail}
                alt=""
                sx={{ width: 96, height: 54 }}
              />
            </Grid>
          }
          <Grid item xs sx={{ minWidth: 0 }}>
            <Typography variant="subtitle1" noWrap>{info.title}</Typography>
            <Typography variant="body2" color="text.secondary" noWrap>
              {info.uploader}
            </Typography>
          </Grid>
        </Grid>
      </Grid>

      <Grid item>
        <FolderField
          value={folder}
          onChange={setFolder}
          error={!!folderError}
          helperText={folderError || (folderInfo ? folderHelp(t, folderInfo, isReorder) : ' ')}
        />
      </Grid>
      <Grid item>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              size="small"
              label={t('import.editor.artist')}
              value={artist}
              onChange={(event) => setArtist(event.target.value)}
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              size="small"
              label={t('import.editor.album')}
              value={album}
              onChange={(event) => setAlbum(event.target.value)}
            />
          </Grid>
        </Grid>
      </Grid>

      <Grid item>
        {hasChapters &&
          <FormControlLabel
            control={<Switch checked={splitChapters} onChange={toggleChapters} />}
            label={t('import.editor.split-chapters', { count: chapterCount })}
          />
        }
        <FormControlLabel
          control={<Switch checked={cover} onChange={(event) => setCover(event.target.checked)} />}
          label={t('import.editor.cover')}
        />
        {exists &&
          <FormControlLabel
            control={<Switch checked={reorder} onChange={(event) => setReorder(event.target.checked)} />}
            label={t('import.editor.reorder')}
          />
        }
      </Grid>

      {info.truncated &&
        <Grid item>
          <Alert severity="info">
            {t('import.editor.truncated', { count: info.entries.length })}
          </Alert>
        </Grid>
      }

      {isReorder &&
        <Grid item>
          <Alert severity="warning">{t('import.editor.reorder-hint')}</Alert>
        </Grid>
      }

      <Grid item>
        <TrackList tracks={tracks} setTracks={setTracks} reorder={isReorder} />
      </Grid>

      {error &&
        <Grid item>
          <Alert severity="error">{error}</Alert>
        </Grid>
      }

      <Grid item>
        <Grid container spacing={1} justifyContent="flex-end">
          <Grid item>
            <Button onClick={() => request('ytimportReset')}>
              {t('import.cancel')}
            </Button>
          </Grid>
          <Grid item>
            <Button
              variant="contained"
              disabled={isStarting || !folderInfo || !!folderError || newCount === 0}
              onClick={startImport}
            >
              {t('import.editor.start', { count: newCount })}
            </Button>
          </Grid>
        </Grid>
      </Grid>
    </Grid>
  );
};

export default Editor;
