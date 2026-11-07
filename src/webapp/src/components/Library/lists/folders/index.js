import React, { useEffect, useState } from "react";
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import {
  CircularProgress,
  Typography,
} from "@mui/material";

import request from '../../../../utils/request';
import FolderList from "./folder-list";
import { useMusicLibraryPath } from '../../now-playing';

const Folders = ({
  musicFilter,
  isSelecting,
  registerMusicToCard,
}) => {
  const { t } = useTranslation();
  const { dir = './' } = useParams();
  const [folders, setFolders] = useState([]);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  // Folder paths are absolute: needed to recognize the library root
  const libraryPath = useMusicLibraryPath();

  const search = ({ name }) => {
    if (musicFilter === '') return true;

    const lowerCaseMusicFilter = musicFilter.toLowerCase();

    return name.toLowerCase().includes(lowerCaseMusicFilter);
  };

  useEffect(() => {
    const fetchFolderList = async () => {
      setIsLoading(true);
      const { result, error } = await request(
        'folderList',
        { folder: decodeURIComponent(dir) }
      );
      setIsLoading(false);

      if(result) setFolders(result);
      if(error) setError(error);
    }

    fetchFolderList();
  }, [dir]);

  const filteredFolders = folders.filter(search);

  if (isLoading) return <CircularProgress />;
  if (error) return <Typography>{t('library.loading-error')}</Typography>;
  if (!filteredFolders.length) {
    if (musicFilter) return <Typography>{`☝️ ${t('library.folders.no-music')}`}</Typography>;
    return <Typography>{`${t('library.folders.empty-folder')} 🙈`}</Typography>;
  }

  return (
    <FolderList
      dir={dir}
      folders={filteredFolders}
      libraryPath={libraryPath}
      isSelecting={isSelecting}
      registerMusicToCard={registerMusicToCard}
    />
  );
};

export default Folders;
