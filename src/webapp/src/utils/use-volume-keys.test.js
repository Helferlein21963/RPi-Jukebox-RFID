import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

import PubSubContext from '../context/pubsub/context';
import request from './request';
import useVolumeKeys, { VOLUME_KEY_STEP } from './use-volume-keys';

// With a factory: an automatic mock would load the real module, which connects the sockets
jest.mock('./request', () => ({ __esModule: true, default: jest.fn() }));

afterEach(() => jest.clearAllMocks());

const Keys = () => {
  useVolumeKeys();
  return <input aria-label="field" />;
};

const renderKeys = (mute = false) => render(
  <PubSubContext.Provider value={{ state: { 'volume.level': { volume: 30, mute } } }}>
    <Keys />
  </PubSubContext.Provider>
);

test('+ / - and the volume keys of the keyboard change the volume', () => {
  renderKeys();

  fireEvent.keyDown(window, { key: '+' });
  fireEvent.keyDown(window, { key: '-' });
  fireEvent.keyDown(window, { key: 'AudioVolumeUp' });
  fireEvent.keyDown(window, { key: 'AudioVolumeDown' });

  expect(request.mock.calls).toEqual([
    ['change_volume', { step: VOLUME_KEY_STEP }],
    ['change_volume', { step: -VOLUME_KEY_STEP }],
    ['change_volume', { step: VOLUME_KEY_STEP }],
    ['change_volume', { step: -VOLUME_KEY_STEP }],
  ]);
});

test('M unmutes when muted', () => {
  renderKeys(true);
  fireEvent.keyDown(window, { key: 'm' });
  expect(request).toHaveBeenCalledWith('toggleMuteVolume', { mute: false });
});

test('the mute key of the keyboard mutes', () => {
  renderKeys(false);
  fireEvent.keyDown(window, { key: 'AudioVolumeMute' });
  expect(request).toHaveBeenCalledWith('toggleMuteVolume', { mute: true });
});

test('a held key is throttled, mute toggles only once', () => {
  renderKeys();
  fireEvent.keyDown(window, { key: '+' });
  fireEvent.keyDown(window, { key: '+', repeat: true });
  fireEvent.keyDown(window, { key: '+', repeat: true });
  expect(request).toHaveBeenCalledTimes(1);

  fireEvent.keyDown(window, { key: 'm' });
  fireEvent.keyDown(window, { key: 'm', repeat: true });
  expect(request).toHaveBeenCalledTimes(2);
});

test('nothing happens while typing, with Ctrl (zoom) or for other keys', () => {
  renderKeys();
  const field = screen.getByLabelText('field');

  fireEvent.keyDown(field, { key: '+' });
  fireEvent.keyDown(field, { key: 'm' });
  fireEvent.keyDown(window, { key: '+', ctrlKey: true });
  fireEvent.keyDown(window, { key: '-', metaKey: true });
  fireEvent.keyDown(window, { key: 'a' });

  expect(request).not.toHaveBeenCalled();
});
