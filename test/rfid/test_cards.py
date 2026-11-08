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


@pytest.fixture
def path_cards(cfg_cards):
    cfg_cards.config_dict({
        'folder': {'alias': 'play_folder', 'args': ['/music/Conni', True], 'name': 'Conni'},
        'inside': {'alias': 'play_card', 'kwargs': {'folder': '/music/Conni/CD 1', 'recursive': False}},
        'song': {'alias': 'play_single', 'args': ['Conni/01.mp3']},
        'raw': {'package': 'player', 'plugin': 'ctrl', 'method': 'play_folder', 'args': ['Conni']},
        'similar': {'alias': 'play_folder', 'args': ['/music/ConniPlus']},
        'album': {'alias': 'play_album', 'args': ['Conni', 'Conni']},
        'volume': {'alias': 'change_volume', 'args': ['/music/Conni']},
    })
    return cfg_cards


@pytest.mark.skipif(sys.platform.startswith('win'), reason='POSIX paths')
def test_rewrite_paths_adapts_cards_playing_the_renamed_path(path_cards, monkeypatch):
    saved = []
    monkeypatch.setattr(path_cards, 'save', lambda *args, **kwargs: saved.append(True))

    assert cards.rewrite_paths('/music/Conni', '/music/Conni 1', '/music') == 4

    assert path_cards['folder'] == {'alias': 'play_folder', 'args': ['/music/Conni 1', True], 'name': 'Conni'}
    assert path_cards['inside']['kwargs'] == {'folder': '/music/Conni 1/CD 1', 'recursive': False}
    assert path_cards['song']['args'] == ['Conni 1/01.mp3']
    assert path_cards['raw']['args'] == ['Conni 1']
    assert path_cards['similar']['args'] == ['/music/ConniPlus']
    assert path_cards['album']['args'] == ['Conni', 'Conni']
    assert path_cards['volume']['args'] == ['/music/Conni']
    assert saved == [True]


@pytest.mark.skipif(sys.platform.startswith('win'), reason='POSIX paths')
def test_rewrite_paths_dry_run_only_counts(path_cards, monkeypatch):
    monkeypatch.setattr(path_cards, 'save', lambda *args, **kwargs: pytest.fail('saved'))

    assert cards.rewrite_paths('/music/Conni', '/music/Conni', '/music', dry_run=True) == 4
    assert path_cards['folder']['args'] == ['/music/Conni', True]


@pytest.mark.skipif(sys.platform.startswith('win'), reason='POSIX paths')
def test_rewrite_paths_many_moves_each_card_once(cfg_cards, monkeypatch):
    saved = []
    monkeypatch.setattr(cfg_cards, 'save', lambda *args, **kwargs: saved.append(True))
    cfg_cards.config_dict({
        'a': {'alias': 'play_single', 'args': ['Maus/a.mp3']},
        'b': {'alias': 'play_single', 'kwargs': {'song_url': '/music/Maus/b.mp3'}},
        'folder': {'alias': 'play_folder', 'args': ['/music/Maus']},
    })

    # a and b swap their names
    renames = [['/music/Maus/a.mp3', '/music/Maus/b.mp3'], ['/music/Maus/b.mp3', '/music/Maus/a.mp3']]
    assert cards.rewrite_paths_many(renames, '/music') == 2

    assert cfg_cards['a']['args'] == ['Maus/b.mp3']
    assert cfg_cards['b']['kwargs'] == {'song_url': '/music/Maus/a.mp3'}
    assert cfg_cards['folder']['args'] == ['/music/Maus']
    assert saved == [True]


@pytest.fixture
def published(cfg_cards, monkeypatch):
    """Topics and payloads sent by the card database"""
    sent = []

    class RecordingPublisher:
        def send(self, topic, payload):
            sent.append((topic, payload))

    monkeypatch.setattr(publishing, 'get_publisher', lambda: RecordingPublisher())
    return sent


def test_changes_publish_a_new_stamp_each(published):
    cards.register_card('new', 'play_folder', args=['/music/B'], auto_save=False)
    cards.delete_card('new', auto_save=False)

    assert [topic for topic, _ in published] == ['cards.database.has_changed'] * 2
    first, second = (payload for _, payload in published)
    assert isinstance(first, float)
    assert second >= first
