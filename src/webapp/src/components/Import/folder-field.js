import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Autocomplete,
  Box,
  TextField,
  Typography,
} from '@mui/material';

import CreateNewFolderOutlinedIcon from '@mui/icons-material/CreateNewFolderOutlined';
import FolderOutlinedIcon from '@mui/icons-material/FolderOutlined';

import request from '../../utils/request';

const MAX_OPTIONS = 50;

// Existing folders matching the input, and first "+ new folder" if the input names none of them
const filterFolders = (folders, input) => {
  const text = input.trim().toLocaleLowerCase();
  const matches = folders
    .filter(({ folder }) => folder.toLocaleLowerCase().includes(text))
    .slice(0, MAX_OPTIONS);
  const exact = folders.some(({ folder }) => folder.toLocaleLowerCase() === text);
  return text && !exact ? [{ folder: input.trim(), isNew: true }, ...matches] : matches;
};

// Folder of the import: type a new name, or pick an existing folder of the music library from the list
const FolderField = ({ value, onChange, error, helperText }) => {
  const { t } = useTranslation();
  const [folders, setFolders] = useState([]);

  useEffect(() => {
    let isCurrent = true;
    const loadFolders = async () => {
      const { result } = await request('ytimportListFolders');
      if (isCurrent && Array.isArray(result)) setFolders(result);
    };
    loadFolders();
    return () => { isCurrent = false; };
  }, []);

  return (
    <Autocomplete
      freeSolo
      fullWidth
      size="small"
      options={folders}
      inputValue={value}
      onInputChange={(event, newValue) => onChange(newValue)}
      onChange={(event, option) => {
        if (option && typeof option === 'object') onChange(option.folder);
      }}
      filterOptions={(options, { inputValue }) => filterFolders(options, inputValue)}
      getOptionLabel={(option) => (typeof option === 'string' ? option : option.folder)}
      isOptionEqualToValue={(option, selected) => option.folder === selected.folder}
      renderOption={(props, option) => (
        <Box
          component="li"
          {...props}
          key={`${option.isNew ? 'new' : 'folder'}:${option.folder}`}
          sx={{ gap: 1, overflowWrap: 'anywhere' }}
        >
          {option.isNew
            ? <CreateNewFolderOutlinedIcon fontSize="small" color="primary" />
            : <FolderOutlinedIcon fontSize="small" color="action" />
          }
          <Box sx={{ flexGrow: 1, minWidth: 0 }}>
            {option.isNew ? t('import.editor.folder-create', { folder: option.folder }) : option.folder}
          </Box>
          {!option.isNew &&
            <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
              {t('import.editor.folder-tracks', { count: option.tracks })}
            </Typography>
          }
        </Box>
      )}
      renderInput={(params) => (
        <TextField
          {...params}
          label={t('import.editor.folder')}
          error={error}
          helperText={helperText}
        />
      )}
    />
  );
};

export default FolderField;
