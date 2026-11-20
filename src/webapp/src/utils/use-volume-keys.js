import { useContext, useEffect, useRef } from 'react';

import PubSubContext from '../context/pubsub/context';
import request from './request';

// Volume step of one key press, in percent
export const VOLUME_KEY_STEP = 5;
// Holding a key down repeats it: then at most one request per this many milliseconds
// (RPC calls are serialized by the core)
export const VOLUME_KEY_INTERVAL_MS = 150;

const UP_KEYS = ['AudioVolumeUp', '+'];
const DOWN_KEYS = ['AudioVolumeDown', '-'];
const MUTE_KEYS = ['AudioVolumeMute', 'm', 'M'];
// The media keys also change the volume of the computer: that can't be prevented
const MEDIA_KEYS = ['AudioVolumeUp', 'AudioVolumeDown', 'AudioVolumeMute'];

// True while the user types into a field, where + / - / m are text
const isTyping = (target) => {
  if (!target) return false;
  const tag = (target.tagName || '').toLowerCase();
  return tag === 'input' || tag === 'textarea' || tag === 'select' || !!target.isContentEditable;
};

// Changes the volume of the box with the keyboard while the Web App is in the foreground:
// volume keys of the keyboard (Fn / media keys) and + / - / M.
// Mobile browsers don't pass the hardware volume buttons of a phone on to web pages.
const useVolumeKeys = () => {
  const { state: { 'volume.level': { mute } = {} } = {} } = useContext(PubSubContext);
  // Read in the listener without registering it again on every volume change
  const muteRef = useRef(mute);
  muteRef.current = mute;
  const lastRequest = useRef(0);

  useEffect(() => {
    const onKeyDown = (event) => {
      const { key } = event;
      const isUp = UP_KEYS.includes(key);
      const isDown = DOWN_KEYS.includes(key);
      const isMute = MUTE_KEYS.includes(key);
      if (!isUp && !isDown && !isMute) return;
      // Ctrl + / - zooms the page; Alt / Meta belong to the browser or the system
      if (event.ctrlKey || event.altKey || event.metaKey) return;
      if (isTyping(event.target)) return;

      if (!MEDIA_KEYS.includes(key)) event.preventDefault();

      if (isMute) {
        // Toggling once per press, not on the repeats of a held key
        if (event.repeat) return;
        request('toggleMuteVolume', { mute: !muteRef.current });
        return;
      }

      const now = Date.now();
      if (event.repeat && now - lastRequest.current < VOLUME_KEY_INTERVAL_MS) return;
      lastRequest.current = now;
      request('change_volume', { step: isUp ? VOLUME_KEY_STEP : -VOLUME_KEY_STEP });
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);
};

export default useVolumeKeys;
