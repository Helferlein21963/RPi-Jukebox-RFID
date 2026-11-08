# RPi-Jukebox-RFID Version 3
# Copyright (c) See file LICENSE in project root folder
"""Tests for the timers (components.timers) and the timer base class (jukebox.multitimer), plugs and publisher mocked"""
import os
import sys
import threading
from unittest import mock

import pytest

# In case this is run locally from
sys.path.append(os.path.abspath('../../src/jukebox'))
import jukebox.plugs as plugs  # noqa: E402

plugs.ALLOW_DIRECT_IMPORTS = True
import jukebox.multitimer as multitimer  # noqa: E402
import components.timers as timers  # noqa: E402


@pytest.fixture
def published():
    """Collect everything the timers publish as (topic, state)"""
    messages = []
    publisher = mock.Mock()
    publisher.send.side_effect = lambda topic, state: messages.append((topic, dict(state)))
    with mock.patch.object(multitimer.publishing, 'get_publisher', return_value=publisher):
        yield messages


def wait_until(predicate, timeout=2.0):
    event = threading.Event()
    for _ in range(int(timeout / 0.01)):
        if predicate():
            return True
        event.wait(0.01)
    return predicate()


# ---------------------------------------------------------------------------
# GenericTimerClass
# ---------------------------------------------------------------------------

def test_timer_runs_function_and_publishes_start_and_end(published):
    done = threading.Event()
    timer = multitimer.GenericTimerClass('test.timer', 0.05, done.set)
    timer.start()
    assert done.wait(2)
    assert wait_until(lambda: not timer.timer_thread.is_alive())
    assert not timer.is_alive()
    states = [state for topic, state in published if topic == 'test.timer']
    assert states[1]['enabled'] is True
    assert states[1]['wait_seconds'] == 0.05
    assert states[-1]['enabled'] is False


def test_timer_state_remaining_seconds(published):
    timer = multitimer.GenericTimerClass('test.timer', 100, mock.Mock())
    assert timer.get_state()['remaining_seconds'] == 0
    timer.start()
    try:
        state = timer.get_state()
        assert state['enabled'] is True
        assert 99 <= state['remaining_seconds'] <= 100
    finally:
        timer.cancel()
    assert timer.get_state() == {'enabled': False, 'remaining_seconds': 0, 'wait_seconds': 100,
                                 'type': 'GenericTimerClass'}


def test_timer_cancel_does_not_call_function(published):
    function = mock.Mock()
    timer = multitimer.GenericTimerClass('test.timer', 100, function)
    timer.start()
    timer.cancel()
    assert not timer.is_alive()
    timer.timer_thread.join(2)
    function.assert_not_called()
    assert published[-1] == ('test.timer', {'enabled': False, 'remaining_seconds': 0, 'wait_seconds': 100,
                                            'type': 'GenericTimerClass'})


def test_timer_restart_right_after_cancel(published):
    """A new start directly after cancel must run, and the end of the old thread must not publish 'disabled'"""
    function = mock.Mock()
    timer = multitimer.GenericTimerClass('test.timer', 100, function)
    timer.start()
    old_thread = timer.timer_thread
    # Keep the old thread from finishing until the new timer runs
    with mock.patch.object(old_thread, 'is_alive', return_value=True):
        timer.cancel()
        timer.start(wait_seconds=50)
        assert timer.timer_thread is not old_thread
        assert timer.is_alive()
    old_thread.join(2)
    try:
        assert timer.is_alive()
        assert wait_until(lambda: published[-1][1]['wait_seconds'] == 50)
        assert published[-1][1]['enabled'] is True
    finally:
        timer.cancel()
    timer.timer_thread.join(2)
    assert published[-1][1]['enabled'] is False
    function.assert_not_called()


def test_timer_start_while_running_is_ignored(published):
    timer = multitimer.GenericTimerClass('test.timer', 100, mock.Mock())
    timer.start()
    thread = timer.timer_thread
    try:
        timer.start(wait_seconds=5)
        assert timer.timer_thread is thread
        assert timer.get_timeout() == 100
    finally:
        timer.cancel()


# ---------------------------------------------------------------------------
# Volume fade out
# ---------------------------------------------------------------------------

@pytest.fixture
def plugs_calls():
    """Mock the plugs calls of the timers module, volume starts at 60"""
    calls = []

    def call(package, plugin, method=None, args=None, kwargs=None):
        calls.append((package, plugin, method, args))
        if (package, plugin, method) == ('volume', 'ctrl', 'get_volume'):
            return 60

    with mock.patch.object(timers.plugin, 'call', side_effect=call), \
            mock.patch.object(timers.plugin, 'call_ignore_errors', side_effect=call):
        yield calls


def volumes(calls):
    return [args[0] for package, plugin, method, args in calls if method == 'set_volume']


def test_fade_action_fades_then_stops_and_restores(plugs_calls):
    action = timers.VolumeFadeOutAction(steps=3)
    action(iteration=2)
    action(iteration=1)
    assert volumes(plugs_calls) == [40, 20]
    action(iteration=0)
    assert volumes(plugs_calls) == [40, 20, 60]
    # Stop before the volume is restored
    assert plugs_calls[-2] == ('player', 'ctrl', 'stop', None)
    assert plugs_calls[-1] == ('volume', 'ctrl', 'set_volume', [60])


def test_fade_action_without_volume_still_stops(plugs_calls):
    with mock.patch.object(timers.plugin, 'call', side_effect=Exception('no volume')):
        action = timers.VolumeFadeOutAction(steps=2)
        action(iteration=1)
        action(iteration=0)
    assert volumes(plugs_calls) == []
    assert ('player', 'ctrl', 'stop', None) in plugs_calls


@pytest.mark.parametrize('wait, fade, expected', [
    (600, 10, (590, 0.5, 20)),     # 10 s fade in 20 steps at the end
    (600, 300, (300, 3, 100)),     # at most 100 steps
    (4, 10, (0, 0.5, 8)),          # fade longer than the timer: the whole time
    (600, 0, (600, 0, 1)),         # no fade: just stop
    (600, 0.2, (599.8, 0.2, 1)),
])
def test_fade_plan(wait, fade, expected):
    delay, interval, steps = timers.fade_plan(wait, fade)
    assert (delay, steps) == pytest.approx((expected[0], expected[2]))
    assert interval == pytest.approx(expected[1])
    assert delay + interval * steps == pytest.approx(wait)


def test_fade_timer_start_with_wait_and_fade_seconds(published, plugs_calls):
    timer = timers.VolumeFadeOutTimerClass('timers.timer_fade_volume', 3600, fade_seconds=10)
    with mock.patch.object(timer, '_start_thread') as start_thread:
        timer.start(wait_seconds=600, fade_seconds=30)
    interval, steps, action = start_thread.call_args[0]
    assert start_thread.call_args[1] == {'delay': 570}
    assert (interval, steps, action.steps) == (0.5, 60, 60)
    assert timer.get_timeout() == 600
    assert timer.get_state()['fade_seconds'] == 30


def test_fade_timer_without_fade_seconds_uses_the_default(published, plugs_calls):
    timer = timers.VolumeFadeOutTimerClass('timers.timer_fade_volume', 3600, fade_seconds=10)
    with mock.patch.object(timer, '_start_thread'):
        timer.start(wait_seconds=600, fade_seconds=30)
    timer.timer_thread = None
    with mock.patch.object(timer, '_start_thread') as start_thread:
        timer.start(wait_seconds=600)
    assert start_thread.call_args[1] == {'delay': 590}
    assert timer.get_state()['fade_seconds'] == 10


def test_fade_timer_runs_to_the_end(published, plugs_calls):
    timer = timers.VolumeFadeOutTimerClass('timers.timer_fade_volume', 1.5, fade_seconds=1)
    timer.start()
    assert wait_until(lambda: timer.timer_thread is not None and not timer.timer_thread.is_alive(), timeout=4)
    assert ('player', 'ctrl', 'stop', None) in plugs_calls
    # 2 steps of 0.5 s after a delay of 0.5 s: one lower volume, then stop and restore
    assert volumes(plugs_calls) == [30, 60]
    state = [state for topic, state in published if topic == 'timers.timer_fade_volume'][-1]
    assert state['enabled'] is False
    assert state['fade_seconds'] == 1
    assert state['type'] == 'VolumeFadeOutTimerClass'


def test_fade_timer_cancel_during_delay(published, plugs_calls):
    timer = timers.VolumeFadeOutTimerClass('timers.timer_fade_volume', 100, fade_seconds=1)
    timer.start()
    timer.cancel()
    timer.timer_thread.join(2)
    assert not timer.timer_thread.is_alive()
    assert plugs_calls == []
    assert published[-1][1]['enabled'] is False
