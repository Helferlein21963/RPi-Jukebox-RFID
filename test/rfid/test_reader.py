# RPi-Jukebox-RFID Version 3
# Copyright (c) See file LICENSE in project root folder
"""Tests for the card read loop of the RFID reader: double reads, unknown cards and routing of music cards"""
import os
import sys
import types

import pytest

# In case this is run locally from
sys.path.append(os.path.abspath('../../src/jukebox'))
import jukebox.plugs as plugs  # noqa: E402
import jukebox.publishing as publishing  # noqa: E402
import jukebox.cfghandler  # noqa: E402

plugs.ALLOW_DIRECT_IMPORTS = True
import components.rfid.reader as reader  # noqa: E402

DELAY = 2.0
FAKE_MODULE = 'fake_test_reader'


class Clock:
    def __init__(self):
        self.now = 1000.0

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class FakeCancel:
    """Replaces the cancel event of the reader thread, so the read loop does not wait in real time"""
    def is_set(self):
        return False

    def wait(self, timeout=None):
        return False

    def set(self):
        pass


def run_reads(monkeypatch, reads):
    """
    Feed card reads through ReaderRunner.run() and return the triggered calls

    :param reads: list of (seconds since previous read, card id)
    """
    clock = Clock()
    calls = []

    class FakeReader:
        def __init__(self, reader_cfg_key):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def __iter__(self):
            for pause, card_id in reads:
                clock.sleep(pause)
                yield card_id

        def stop(self):
            pass

    module = types.ModuleType(f'components.rfid.hardware.{FAKE_MODULE}.{FAKE_MODULE}')
    module.ReaderClass = FakeReader
    monkeypatch.setitem(sys.modules, f'components.rfid.hardware.{FAKE_MODULE}', types.ModuleType(FAKE_MODULE))
    monkeypatch.setitem(sys.modules, f'components.rfid.hardware.{FAKE_MODULE}.{FAKE_MODULE}', module)

    def fake_call(package, plugin, method, args=None, kwargs=None):
        calls.append((f"{package}.{plugin}.{method}", tuple(args or ()), kwargs or {}))

    class FakePublisher:
        def send(self, topic, payload):
            calls.append(('publish', payload))

    monkeypatch.setattr(reader, 'time', clock)
    monkeypatch.setattr(plugs, 'call_ignore_errors', fake_call)
    monkeypatch.setattr(plugs, 'loaded_as', lambda name: 'rfid')
    monkeypatch.setattr(publishing, 'get_publisher', lambda: FakePublisher())

    jukebox.cfghandler.get_handler('rfid').config_dict(
        {'rfid': {'readers': {'read_test': {
            'module': FAKE_MODULE,
            'same_id_delay': DELAY,
            'place_not_swipe': {'enabled': False, 'card_removal_action': {'alias': 'pause'}}}}}})
    jukebox.cfghandler.get_handler('cards').config_dict({
        'music': {'alias': 'play_folder', 'args': ['/music/A']},
        'music2': {'alias': 'play_folder', 'kwargs': {'folder': '/music/B', 'recursive': True}},
        'next': {'alias': 'next_song'},
        'volume': {'alias': 'change_volume', 'args': [5], 'ignore_same_id_delay': True},
    })

    runner = reader.ReaderRunner('read_test')
    runner._cancel = FakeCancel()
    runner.run()
    return [c for c in calls if c[0] != 'publish']


def player_calls(calls):
    return [c[0] for c in calls]


def test_play_folder_card_is_routed_through_play_card(monkeypatch):
    calls = run_reads(monkeypatch, [(0, 'music'), (5, 'music2')])
    assert calls == [('player.ctrl.play_card', ('/music/A',), {}),
                     ('player.ctrl.play_card', (), {'folder': '/music/B', 'recursive': True})]


def test_double_read_on_placing_is_ignored(monkeypatch):
    # Measured on a USB reader: placing a card gives 2 reads ~0.6s apart
    calls = run_reads(monkeypatch, [(0, 'music'), (0.6, 'music')])
    assert player_calls(calls) == ['player.ctrl.play_card']


def test_repeated_reads_extend_the_delay(monkeypatch):
    # Every read restarts same_id_delay, so a wobbling card does not trigger again
    calls = run_reads(monkeypatch, [(0, 'music'), (1.5, 'music'), (1.5, 'music'), (1.5, 'music')])
    assert player_calls(calls) == ['player.ctrl.play_card']


def test_second_swipe_after_delay_goes_to_play_card(monkeypatch):
    # play_card decides about pause / resume, as only the player knows its state
    calls = run_reads(monkeypatch, [(0, 'music'), (0.6, 'music'), (5, 'music'), (0.6, 'music')])
    assert player_calls(calls) == ['player.ctrl.play_card', 'player.ctrl.play_card']


def test_unknown_card_triggers_no_player_action(monkeypatch):
    calls = run_reads(monkeypatch, [(0, 'unknown'), (4, 'unknown'), (4, 'unknown')])
    assert calls == []


def test_command_card_repeats_its_command(monkeypatch):
    calls = run_reads(monkeypatch, [(0, 'next'), (0.5, 'next'), (3, 'next')])
    assert player_calls(calls) == ['player.ctrl.next', 'player.ctrl.next']


def test_card_with_ignore_same_id_delay_triggers_every_read(monkeypatch):
    calls = run_reads(monkeypatch, [(0, 'volume'), (0.3, 'volume'), (0.3, 'volume')])
    assert player_calls(calls) == ['volume.ctrl.change_volume'] * 3


def test_other_card_in_between_is_a_new_read(monkeypatch):
    calls = run_reads(monkeypatch, [(0, 'music'), (0.5, 'next'), (0.5, 'music')])
    assert player_calls(calls) == ['player.ctrl.play_card', 'player.ctrl.next', 'player.ctrl.play_card']


@pytest.fixture
def rfid_cfg(monkeypatch):
    handler = jukebox.cfghandler.get_handler('rfid')
    handler.config_dict({'rfid': {'readers': {
        'read_a': {'module': 'x', 'same_id_delay': 1.0},
        'read_b': {'module': 'y'}}}})
    monkeypatch.setattr(handler, 'save', lambda only_if_changed=False: None)
    return handler


def test_set_same_id_delay_applies_to_all_readers(monkeypatch, rfid_cfg):
    runner = types.SimpleNamespace(_cfg_same_id_delay=1.0)
    monkeypatch.setitem(reader._READERS, 'read_a', runner)

    assert reader.get_same_id_delay() == 1.0
    assert reader.set_same_id_delay('3.5') == 3.5

    assert reader.get_same_id_delay() == 3.5
    assert rfid_cfg.getn('rfid', 'readers', 'read_b', 'same_id_delay') == 3.5
    assert runner._cfg_same_id_delay == 3.5


@pytest.mark.parametrize('delay', [-1, 11])
def test_set_same_id_delay_rejects_out_of_range(rfid_cfg, delay):
    with pytest.raises(ValueError):
        reader.set_same_id_delay(delay)
    assert reader.get_same_id_delay() == 1.0


@pytest.mark.parametrize('action, expected', [
    ({'package': 'player', 'plugin': 'ctrl', 'method': 'play_folder', 'args': ['x'], 'kwargs': {}}, 'play_card'),
    ({'package': 'player', 'plugin': 'ctrl', 'method': 'play_album', 'args': [], 'kwargs': {}}, 'play_album'),
    ({'package': 'volume', 'plugin': 'ctrl', 'method': 'play_folder', 'args': [], 'kwargs': {}}, 'play_folder'),
])
def test_swipe_aware_action(action, expected):
    assert reader.swipe_aware_action(action)['method'] == expected
