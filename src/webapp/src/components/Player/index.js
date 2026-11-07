import React, { useContext, useEffect, useState } from 'react';

import Grid from '@mui/material/Grid';

import Cover from './cover';
import Controls from './controls';
import Display from './display';
import SeekBar from './seekbar';
import Volume from './volume';

import PlayerContext from '../../context/player/context';
import request from '../../utils/request';

const Player = () => {
  const { state: { playerstatus } } = useContext(PlayerContext);
  const { file } = playerstatus || {};

  const [coverImage, setCoverImage] = useState(undefined);
  const [backgroundImage, setBackgroundImage] = useState('none');

  useEffect(() => {
    // Set when the song changes again before the request returns, so a late reply
    // for the previous song can't overwrite the cover of the current one
    let outdated = false;

    const showCover = (filename) => {
      if (outdated) return;
      if (filename) {
        setCoverImage(`/cover-cache/${filename}`);
        setBackgroundImage([
          'linear-gradient(to bottom, rgba(18, 18, 18, 0.5), rgba(18, 18, 18, 1))',
          `url(/cover-cache/${filename})`
        ].join(','));
      } else {
        // No cover for this song: don't keep showing the previous song's cover
        setCoverImage(undefined);
        setBackgroundImage('none');
      }
    };

    const getCoverArt = async () => {
      const { result } = await request('getSingleCoverArt', { song_url: file });
      showCover(result);
    };

    if (file) {
      getCoverArt();
    } else {
      showCover(undefined);
    }

    return () => { outdated = true; };
  }, [file]);

  return (
    <Grid
      container
      id="player"
      sx={{
        backgroundImage,
        backgroundPosition: 'center',
      }}
    >
      <Grid
        container
        sx={{
          paddingTop: '30px',
          paddingLeft: '30px',
          paddingRight: '30px',
          minHeight: 'calc(100vh - 64px - 10px)',
          backdropFilter: 'blur(25px)',
        }}
      >
        <Grid item xs={12} sm={5}>
          <Cover coverImage={coverImage} />
        </Grid>
        <Grid item xs={12} sm={7}>
          <Display />
          <SeekBar />
          <Controls />
          <Volume />
        </Grid>
      </Grid>
    </Grid>
  );
};

export default Player;
