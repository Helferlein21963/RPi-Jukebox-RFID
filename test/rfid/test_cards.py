# RPi-Jukebox-RFID Version 3
# Copyright (c) See file LICENSE in project root folder
"""Tests for the card database plugin: card names"""
import os
import sys

import pytest

# In case this is run locally from
sys.path.append(os.path.abspath('../../src/jukebox'))
import jukebox.plugs as plugs  # noqa: E402
import jukebox.publishing as publishing  # noqa: E402
import jukebox.cfghandler  # noqa: E402

plugs.ALLOW_DIRECT_IMPORTS = True
import components.rfid.cards as cards  # noqa: E402


class FakePublisher:
    def send(self, topic, payload):
        pass


@pytest.fixture
def cfg_cards(monkeypatch):
    monkeypatch.setattr(plugs, 'loaded_as', lambda name: 'cards')
    monkeypatch.setattr(plugs, 'get', lambda *args: (lambda: None))
    monkeypatch.setattr(publishing, 'get_publisher', lambda: FakePublisher())
    handler = jukebox.cfghandler.get_handler('cards')
    handler.config_dict({'lion': {'alias': 'play_folder', 'args': ['/music/A'], 'name': 'Lion'}})
    return handler


def test_register_card_stores_name(cfg_cards):
    cards.register_card('new', 'play_folder', args=['/music/B'], name=' Elephant ', auto_save=False)
    assert cfg_cards['new'] == {'alias': 'play_folder', 'name': 'Elephant', 'args': ['/music/B']}
    assert cards.list_cards()['new']['name'] == 'Elephant'


def test_register_card_without_name_keeps_existing_name(cfg_cards):
    cards.register_card('lion', 'play_folder', args=['/music/C'], overwrite=True, auto_save=False)
    assert cfg_cards['lion'] == {'alias': 'play_folder', 'name': 'Lion', 'args': ['/music/C']}


def test_register_card_with_empty_name_removes_name(cfg_cards):
    cards.register_card('lion', 'play_folder', args=['/music/A'], overwrite=True, auto_save=False, name='')
    assert 'name' not in cfg_cards['lion']
    assert 'name' not in cards.list_cards()['lion']


def test_register_card_stores_kwargs(cfg_cards):
    cards.register_card('vol', 'change_volume', kwargs={'step': 5}, auto_save=False)
    assert cfg_cards['vol'] == {'alias': 'change_volume', 'kwargs': {'step': 5}}
