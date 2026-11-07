# RPi-Jukebox-RFID Version 3
# Copyright (c) See file LICENSE in project root folder
"""Tests for the signal handler of the daemon: orderly shutdown also when systemd sends SIGTERM several times"""
import os
import signal
import sys

import pytest

# In case this is run locally from
sys.path.append(os.path.abspath('../../src/jukebox'))
import jukebox.daemon as daemon  # noqa: E402


class Clock:
    def __init__(self):
        self.now = 100.0

    def monotonic(self):
        return self.now


@pytest.fixture
def box(monkeypatch):
    """A JukeBox with only the state the signal handler needs (no plugins, no config)"""
    clock = Clock()
    monkeypatch.setattr(daemon.time, 'monotonic', clock.monotonic)
    jb = daemon.JukeBox.__new__(daemon.JukeBox)
    jb._signal_counter = daemon.itertools.count(1)
    jb._last_signal_time = None
    jb.shutdowns = []
    monkeypatch.setattr(jb, 'exit_gracefully', lambda esignal, timeout: jb.shutdowns.append(esignal), raising=False)
    jb.clock = clock
    return jb


def test_signal_starts_orderly_shutdown(box):
    with pytest.raises(SystemExit) as exc:
        box.signal_handler(signal.SIGTERM, None)
    assert exc.value.code == 0
    assert box.shutdowns == [signal.SIGTERM]


def test_duplicate_signal_during_handler_does_not_prevent_shutdown(box, monkeypatch):
    # Seen on the box: a second SIGTERM interrupted the handler while it was logging. Before the fix,
    # the handler then saw count 2 and nobody started the shutdown -> SIGKILL by systemd after 90 s
    original_debug = daemon.logger.debug
    nested = []

    def debug_with_second_signal(msg, *args, **kwargs):
        if not nested:
            nested.append(msg)
            box.signal_handler(signal.SIGTERM, None)
        original_debug(msg, *args, **kwargs)

    monkeypatch.setattr(daemon.logger, 'debug', debug_with_second_signal)
    with pytest.raises(SystemExit) as exc:
        box.signal_handler(signal.SIGTERM, None)
    assert nested
    assert exc.value.code == 0
    assert box.shutdowns == [signal.SIGTERM]


def test_duplicates_are_ignored_and_later_signals_count(box):
    with pytest.raises(SystemExit):
        box.signal_handler(signal.SIGTERM, None)
    # Same stop request, delivered again via another thread: ignored
    box.signal_handler(signal.SIGTERM, None)
    # A real second Ctrl-C later on: only a hint, no second shutdown
    box.clock.now += 1
    box.signal_handler(signal.SIGINT, None)
    assert box.shutdowns == [signal.SIGTERM]
    # Third Ctrl-C: hard exit
    box.clock.now += 1
    with pytest.raises(SystemExit) as exc:
        box.signal_handler(signal.SIGINT, None)
    assert exc.value.code == 1
    assert box.shutdowns == [signal.SIGTERM]
