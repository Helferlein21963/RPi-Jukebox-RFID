import React from 'react';
import { useTranslation } from 'react-i18next';

import { Alert, AlertTitle } from '@mui/material';

const FailedTracks = ({ failed }) => {
  const { t } = useTranslation();

  return (
    <Alert severity="warning">
      <AlertTitle>{t('import.result.failed')}</AlertTitle>
      {failed.map(({ title, error }, idx) => (
        <div key={idx}><strong>{title}</strong>: {error}</div>
      ))}
    </Alert>
  );
};

export default FailedTracks;
