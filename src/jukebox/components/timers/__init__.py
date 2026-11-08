# RPi-Jukebox-RFID Version 3
# Copyright (c) See file LICENSE in project root folder
"""Timers: shut down, stop the player or fade out the volume and stop the player after a given time

Each timer is a plugin (``timers.timer_shutdown``, ``timers.timer_stop_player``, ``timers.timer_fade_volume``)
with the methods ``start(wait_seconds)``, ``cancel``, ``toggle`` and ``get_state``.
The fade out timer also takes the fade duration: ``start(wait_seconds, fade_seconds)``.
Every start and end is published on the topic of the timer's name (e.g. ``timers.timer_shutdown``).
"""

import logging
from typing import Optional

import jukebox.cfghandler
import jukebox.plugs as plugin
from jukebox.multitimer import GenericTimerClass


logger = logging.getLogger('jb.timers')
cfg = jukebox.cfghandler.get_handler('jukebox')

#: Target time between two volume steps of the fade out
FADE_STEP_SECONDS = 0.5
#: Most volume steps of a fade out (the volume has 100 levels)
FADE_MAX_STEPS = 100
#: Fade out duration if neither the call nor the config set one
FADE_DEFAULT_SECONDS = 10


# ---------------------------------------------------------------------------
# Action functions for Timers
# ---------------------------------------------------------------------------
def shutdown():
    logger.info("Shutting down on timer request...")
    plugin.call_ignore_errors('host', 'shutdown')


def stop_player():
    logger.info("Stopping the player on timer request...")
    plugin.call_ignore_errors('player', 'ctrl', 'stop')


class VolumeFadeOutAction:
    """Timer action: lower the volume in ``steps`` steps, then stop the player

    Called with the decreasing ``iteration`` (``steps - 1`` ... ``0``).
    After the stop, the volume is set back to its value at the start of the fade,
    so the next playback is not silent.
    """

    def __init__(self, steps: int):
        self.steps = steps
        self.start_volume = None

    def __call__(self, iteration):
        if self.start_volume is None:
            # Read the volume only when the fade begins: it may have been changed since the timer started
            try:
                self.start_volume = int(plugin.call('volume', 'ctrl', 'get_volume'))
            except Exception as e:
                logger.error(f"Volume fade out: cannot get the volume: {e}")
                self.start_volume = -1
            logger.info(f"Fading out the volume from {self.start_volume} on timer request...")
        if iteration > 0:
            if self.start_volume > 0:
                volume = round(self.start_volume * iteration / self.steps)
                plugin.call_ignore_errors('volume', 'ctrl', 'set_volume', args=[volume])
            return
        stop_player()
        if self.start_volume >= 0:
            plugin.call_ignore_errors('volume', 'ctrl', 'set_volume', args=[self.start_volume])


def fade_plan(wait_seconds: float, fade_seconds: float):
    """Split a fade out timer into (delay, interval, steps)

    The timer waits ``delay`` seconds, then lowers the volume ``steps`` times every ``interval`` seconds
    (the last step stops the player). In total this takes ``wait_seconds``;
    a fade longer than the wait time takes the whole wait time.
    """
    wait_seconds = max(0.0, float(wait_seconds))
    fade = min(max(0.0, float(fade_seconds)), wait_seconds)
    steps = max(1, min(FADE_MAX_STEPS, round(fade / FADE_STEP_SECONDS)))
    return wait_seconds - fade, fade / steps, steps


class VolumeFadeOutTimerClass(GenericTimerClass):
    """Timer that fades out the volume during the last ``fade_seconds`` of the wait time and then stops the player

    If the wait time is shorter than ``fade_seconds``, the fade takes the whole wait time.
    """

    def __init__(self, name, wait_seconds: float, fade_seconds: float):
        self._default_fade_seconds = fade_seconds
        self._fade_seconds = fade_seconds
        super().__init__(name, wait_seconds, None)

    @plugin.tag
    def start(self, wait_seconds=None, fade_seconds=None):
        """Start the timer

        :param wait_seconds: Time until the player stops (default: the last or configured time)
        :param fade_seconds: Fade out duration at the end of that time, for this run only
            (default: ``timers.volume_fade_out.fade_duration_sec``)
        """
        if self.is_alive():
            logger.error(f"Timer '{self._name}' started! Ignoring start command.")
            return
        if wait_seconds is not None:
            self._wait_seconds = wait_seconds
        self._fade_seconds = self._default_fade_seconds if fade_seconds is None else fade_seconds
        delay, interval, steps = fade_plan(self._wait_seconds, self._fade_seconds)
        self._start_thread(interval, steps, VolumeFadeOutAction(steps), delay=delay)

    @plugin.tag
    def get_state(self):
        """Get the current state and config as dictionary"""
        state = super().get_state()
        state['fade_seconds'] = self._fade_seconds
        state['type'] = 'VolumeFadeOutTimerClass'
        return state


# ---------------------------------------------------------------------------
# Create the timers
# ---------------------------------------------------------------------------
# Created in finalize
timer_shutdown: Optional[GenericTimerClass] = None
timer_stop_player: Optional[GenericTimerClass] = None
timer_fade_volume: Optional[VolumeFadeOutTimerClass] = None


@plugin.finalize
def finalize():
    # Create the various timers with fitting doc for plugin reference
    global timer_shutdown
    timeout = cfg.setndefault('timers', 'shutdown', 'default_timeout_sec', value=60 * 60)
    timer_shutdown = GenericTimerClass(f"{plugin.loaded_as(__name__)}.timer_shutdown",
                                       timeout, shutdown)
    timer_shutdown.__doc__ = "Timer for automatic shutdown"
    # Note: Since timer_shutdown is an instance of a class from a different module,
    # auto-registration would register it with that module. Manually set package to this plugin module
    plugin.register(timer_shutdown, name='timer_shutdown', package=plugin.loaded_as(__name__))

    global timer_stop_player
    timeout = cfg.setndefault('timers', 'stop_player', 'default_timeout_sec', value=60 * 60)
    timer_stop_player = GenericTimerClass(f"{plugin.loaded_as(__name__)}.timer_stop_player",
                                          timeout, stop_player)
    timer_stop_player.__doc__ = "Timer for automatic player stop"
    plugin.register(timer_stop_player, name='timer_stop_player', package=plugin.loaded_as(__name__))

    global timer_fade_volume
    timeout = cfg.setndefault('timers', 'volume_fade_out', 'default_timeout_sec', value=60 * 60)
    fade_seconds = cfg.setndefault('timers', 'volume_fade_out', 'fade_duration_sec', value=FADE_DEFAULT_SECONDS)
    timer_fade_volume = VolumeFadeOutTimerClass(f"{plugin.loaded_as(__name__)}.timer_fade_volume",
                                                timeout, fade_seconds)
    timer_fade_volume.__doc__ = "Timer for a volume fade out and player stop"
    plugin.register(timer_fade_volume, name='timer_fade_volume', package=plugin.loaded_as(__name__))

    # The idle Timer does work in a little sneaky way
    # Idle is when there are no calls through the plugin module
    # Ahh, but also when music is playing this is not idle...
    # Use setattr to replace plugin._call with a plugin._call that saves last access time

    # Three options:
    # (a) whenever a call happens -> restart timer
    # (b) save last call access time -> when timer times out, check that time with timer and restart if necessary with
    # (c) Sniffer on Publisher -> If nothing happens for ages
    #     Most efficient would be a measure the time in the Publisher and use a callback
    # (d) PubSub starts a Timer with target=shutdown. Timer can reset time via function call
    # delta time

    # MPD


@plugin.atexit
def atexit(**ignored_kwargs):
    timer_shutdown.cancel()
    timer_stop_player.cancel()
    timer_fade_volume.cancel()
    return [timer_shutdown.timer_thread, timer_stop_player.timer_thread, timer_fade_volume.timer_thread]
