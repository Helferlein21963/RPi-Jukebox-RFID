# RPi-Jukebox-RFID Version 3
# Copyright (c) See file LICENSE in project root folder
"""A failing button action must not break the event handling of the buttons"""
import os
import sys
import logging

from gpiozero import Device
from gpiozero.pins.mock import MockFactory, MockPin

# In case this is run locally from
sys.path.append(os.path.abspath('../../src/jukebox'))
from components.gpio.gpioz.core.input_devices import Button, _log_exceptions  # noqa: E402

Device.pin_factory = MockFactory(pin_class=MockPin)


def failing_action():
    raise RuntimeError("Not playing")


def test_log_exceptions_passes_arguments_and_result():
    wrapped = _log_exceptions(lambda a, b=0: a + b, 'Dev.on_press')
    assert wrapped(1, b=2) == 3


def test_log_exceptions_logs_instead_of_raising(caplog):
    wrapped = _log_exceptions(failing_action, 'NextSong.on_press')
    with caplog.at_level(logging.ERROR, logger='jb.gpioz'):
        assert wrapped() is None
    assert "Action 'NextSong.on_press' failed: RuntimeError: Not playing" in caplog.text


def test_button_keeps_working_after_failing_action():
    calls = []

    def action():
        calls.append(1)
        if len(calls) == 1:
            failing_action()

    button = Button(5, name='NextSong')
    button.on_press = _log_exceptions(action, 'NextSong.on_press')
    try:
        for _ in range(2):
            button.pin.drive_low()
            button.pin.drive_high()
        assert len(calls) == 2
    finally:
        button.close()
