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
import TrackList from './track-list';
import { buildTracks, chaptersOf, toImportTracks } from './utils';

const Editor = ({ info }) => {
  const { t } = useTranslation();

  const chapterCount = chaptersOf(info).length;
  const hasChapters = chapterCount > 1;

  const [folder, setFolder] = useState(info.title || info.folder);
  const [folderCheck, setFolderCheck] = useState({ folder: info.folder, exists: false });
  const [artist, setArtist] = useState(info.uploader || '');
  const [album, setAlbum] = useState(info.title || '');
  const [splitChapters, setSplitChapters] = useState(hasChapters);
  const [cover, setCover] = useState(true);
  const [tracks, setTracks] = useState(buildTracks(info, hasChapters));
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState(null);

  // The folder name as the core will create it (umlauts written out, no spaces), and whether it exists
  useEffect(() => {
    let isCurrent = true;
    const timer = setTimeout(async () => {
      const { result } = await request('ytimportCheckFolder', { name: folder });
      if (isCurrent && result) setFolderCheck(result);
    }, 400);
    return () => {
      isCurrent = false;
      clearTimeout(timer);
    };
  }, [folder]);

  const toggleChapters = (event) => {
    setSplitChapters(event.target.checked);
    setTracks(buildTracks(info, event.target.checked));
  };

  const importTracks = toImportTracks(tracks);
  const folderError = !folderCheck.folder
    ? t('import.editor.folder-empty')
    : (folderCheck.exists ? t('import.editor.folder-exists', { folder: folderCheck.folder }) : null);

  const startImport = async () => {
    setIsStarting(true);
    setError(null);
    const { error } = await request('ytimportStart', {
      folder,
      tracks: importTracks,
      artist,
      album,
      cover,
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
        <TextField
          fullWidth
          size="small"
          label={t('import.editor.folder')}
          value={folder}
          onChange={(event) => setFolder(event.target.value)}
          error={!!folderError}
          helperText={folderError || t('import.editor.folder-preview', { folder: folderCheck.folder })}
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
      </Grid>

      {info.truncated &&
        <Grid item>
          <Alert severity="info">
            {t('import.editor.truncated', { count: info.entries.length })}
          </Alert>
        </Grid>
      }

      <Grid item>
        <TrackList tracks={tracks} setTracks={setTracks} />
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
              disabled={isStarting || !!folderError || importTracks.length === 0}
              onClick={startImport}
            >
              {t('import.editor.start', { count: importTracks.length })}
            </Button>
          </Grid>
        </Grid>
      </Grid>
    </Grid>
  );
};

export default Editor;
