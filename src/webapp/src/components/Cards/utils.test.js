import React from 'react';
import { render } from '@testing-library/react';

import SliderSetTimer from './controls/actions/timers/slider-set-timer';
import { buildActionData, getSelectableActions, getSelectableCommands } from './utils';

jest.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key) => key }),
}));

describe('selectable card actions', () => {
  it('hides disabled actions and commands', () => {
    expect(getSelectableActions()).toEqual(['play_music', 'audio', 'host', 'timers']);
    expect(getSelectableCommands('audio')).not.toContain('toggle_output');
    expect(getSelectableCommands('audio')).toContain('change_volume');
    expect(getSelectableCommands('timers')).toEqual(['timer_shutdown', 'timer_stop_player', 'timer_fade_volume']);
  });

  it('keeps a disabled action or command a card already uses', () => {
    expect(getSelectableActions('synchronisation')).toContain('synchronisation');
    // The commands of a disabled action stay selectable once the action is chosen
    expect(getSelectableCommands('synchronisation', 'sync_rfidcards_all'))
      .toEqual(['sync_rfidcards_all', 'sync_rfidcards_change_on_rfid_scan']);
    expect(getSelectableCommands('audio', 'toggle_output')).toContain('toggle_output');
  });

  it('has no commands for an unknown action', () => {
    expect(getSelectableCommands(undefined)).toEqual([]);
  });
});

describe('timer card', () => {
  const renderTimer = (args) => {
    const handleActionDataChange = jest.fn();
    render(
      <SliderSetTimer
        actionData={buildActionData('timers', 'timer_shutdown', args)}
        handleActionDataChange={handleActionDataChange}
      />
    );
    return handleActionDataChange;
  };

  it('sets a wait time for a new card', () => {
    expect(renderTimer({})).toHaveBeenCalledWith('timers', 'timer_shutdown', { wait_seconds: 3600 });
  });

  it('replaces the wait time 0 (off), which would shut down at once', () => {
    expect(renderTimer([0])).toHaveBeenCalledWith('timers', 'timer_shutdown', { wait_seconds: 3600 });
  });

  it('keeps a stored wait time', () => {
    expect(renderTimer([600])).not.toHaveBeenCalled();
  });
});
