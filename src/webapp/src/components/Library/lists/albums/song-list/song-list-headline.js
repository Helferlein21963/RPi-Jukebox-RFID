import React from 'react';

import {
  Grid,
  Typography,
} from '@mui/material';

import { CardChips } from '../../../library-cards';

// Title of the album with the cards that play it
const SongListHeadline = ({ artist, album, cards = [] }) => (
  <Grid container sx={{ padding: '16px 8px 0' }}>
    <Grid item>
      <Typography variant="h6" sx={{ fontWeight: 'bold' }} component="h1">
        {album}
      </Typography>
      <Typography>{artist}</Typography>
      <CardChips cards={cards} sx={{ marginTop: '8px' }} />
    </Grid>
  </Grid>
);

export default SongListHeadline;
