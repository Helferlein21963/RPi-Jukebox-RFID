import React from 'react';

import PowerSettingsNewIcon from '@mui/icons-material/PowerSettingsNew';
import StopCircleOutlinedIcon from '@mui/icons-material/StopCircleOutlined';
import VolumeDownIcon from '@mui/icons-material/VolumeDown';

const icons = {
  'shutdown': PowerSettingsNewIcon,
  'stop-player': StopCircleOutlinedIcon,
  'fade-volume': VolumeDownIcon,
};

const TimerIcon = ({ type, ...props }) => {
  const Icon = icons[type];
  return Icon ? <Icon {...props} /> : null;
};

export default TimerIcon;
