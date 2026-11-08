import { useCallback, useContext, useEffect, useRef, useState } from 'react';

import PubSubContext from '../../../context/pubsub/context';
import request from '../../../utils/request';

// Timer types, in display order
const TIMER_TYPES = ['shutdown', 'stop-player', 'fade-volume'];

// 'stop-player' -> 'timer_stop_player' (plugin name and command key)
const pluginName = (type) => `timer_${type.replace('-', '_')}`;

// Topic the core publishes the timer state on
const topicName = (type) => `timers.${pluginName(type)}`;

// Convert a timer state of the core into local state, with the end as local timestamp
const toTimer = (state, receivedAt) => ({
  enabled: !!state?.enabled,
  totalSeconds: state?.wait_seconds || 0,
  endsAt: receivedAt + (state?.remaining_seconds || 0) * 1000,
  fadeSeconds: state?.fade_seconds,
});

// State of all timers (from get_state and the published updates), start and cancel
const useTimers = () => {
  const { state: pubsub } = useContext(PubSubContext);
  const [timers, setTimers] = useState({});
  const [error, setError] = useState(null);

  const applyState = useCallback((type, state) => {
    setTimers((timers) => ({ ...timers, [type]: toTimer(state, Date.now()) }));
  }, []);

  const refresh = useCallback(async (type) => {
    const { result, error } = await request(`${pluginName(type)}.get_state`);
    if (error) return setError(error);
    applyState(type, result);
  }, [applyState]);

  const refreshAll = useCallback(() => {
    TIMER_TYPES.forEach(refresh);
  }, [refresh]);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  // Published updates (timers can also be started by cards, GPIO or the HTTP API).
  // Messages already in the context when the page opened are stale; get_state covers them.
  const [shutdown, stopPlayer, fadeVolume] = TIMER_TYPES.map((type) => pubsub[topicName(type)]);
  const seen = useRef([shutdown, stopPlayer, fadeVolume]);
  useEffect(() => {
    [shutdown, stopPlayer, fadeVolume].forEach((message, index) => {
      if (message && message !== seen.current[index]) {
        seen.current[index] = message;
        applyState(TIMER_TYPES[index], message);
      }
    });
  }, [shutdown, stopPlayer, fadeVolume, applyState]);

  // options: further arguments of the start command (fade out timer: fade_seconds)
  const start = async (type, seconds, options = {}) => {
    setError(null);
    // A running timer of the same type is restarted with the new time
    if (timers[type]?.enabled) {
      await request(`${pluginName(type)}.cancel`);
    }
    const { error } = await request(pluginName(type), { wait_seconds: seconds, ...options });
    if (error) setError(error);
    await refresh(type);
  };

  const cancel = async (type) => {
    setError(null);
    const { error } = await request(`${pluginName(type)}.cancel`);
    if (error) setError(error);
    await refresh(type);
  };

  return { timers, error, start, cancel, refreshAll };
};

export {
  TIMER_TYPES,
  useTimers,
};
