import React, { useEffect, useRef, useState } from "react";
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import {
  CircularProgress,
  Typography,
} from "@mui/material";

import request from '../../../../utils/request';
import { useLibraryChanges } from '../../../../utils/use-updates';
import FolderList from "./folder-list";
import { useMusicLibraryPath } from '../../now-playing';
import { sortFolders } from '../../sort';

const Folders = ({
  musicFilter,
  sort,
  isSelecting,
  registerMusicToCard,
}) => {
  const { t } = useTranslation();
  const { dir = './' } = useParams();
  const [folders, setFolders] = useState([]);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  // Increased to load the folder again (e.g. after renaming a song)
  const [reloadCount, setReloadCount] = useState(0);
  // Changes of the library, also from other devices or files changed on the box
  const libraryChanges = useLibraryChanges();
  const loadedDir = useRef(undefined);
  // Folder paths are absolute: needed to recognize the library root
  const libraryPath = useMusicLibraryPath();

  const search = ({ name }) => {
    if (musicFilter === '') return true;

    const lowerCaseMusicFilter = musicFilter.toLowerCase();

    return name.toLowerCase().includes(lowerCaseMusicFilter);
  };

  useEffect(() => {
    let isCurrent = true;
    const fetchFolderList = async () => {
      // Loading the same folder again: keep showing it (and the scroll position) until the new list is there
      if (loadedDir.current !== dir) setIsLoading(true);
      const { result, error } = await request(
        'folderList',
        { folder: decodeURIComponent(dir) }
      );
      // Another folder was opened meanwhile
      if (!isCurrent) return;
      loadedDir.current = dir;
      setIsLoading(false);

      if(result) {
        setFolders(result);
        setError(null);
      }
      if(error) setError(error);
    }

    fetchFolderList();
    return () => { isCurrent = false; };
  }, [dir, reloadCount, libraryChanges]);

  // Subfolders, then the songs, in the chosen order (A–Z: the songs as they are played)
  const filteredFolders = sortFolders(folders.filter(search), sort);

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
      onChanged={() => setReloadCount((count) => count + 1)}
    />
  );
};

export default Folders;
