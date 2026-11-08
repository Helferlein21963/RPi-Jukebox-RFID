# RPi-Jukebox-RFID Version 3
# Copyright (c) See file LICENSE in project root folder
"""Tests for publishing changes of the music library (PlayerMPD._check_library_update)"""
import os
import sys
import threading
from unittest import mock

import pytest

# In case this is run locally from
sys.path.append(os.path.abspath('../../src/jukebox'))
import jukebox.plugs as plugs  # noqa: E402
import jukebox.publishing as publishing  # noqa: E402

plugs.ALLOW_DIRECT_IMPORTS = True
import components.playermpd as playermpd  # noqa: E402

IDLE = {'state': 'stop'}
UPDATING = {'state': 'stop', 'updating_db': '1'}


@pytest.fixture
def publisher(monkeypatch):
    pub = mock.Mock()
    monkeypatch.setattr(publishing, 'get_publisher', lambda: pub)
    return pub


@pytest.fixture
def player():
    p = playermpd.PlayerMPD.__new__(playermpd.PlayerMPD)
    p.mpd_client = mock.Mock()
    p.mpd_client.stats.return_value = {'db_update': '1000'}
    p.mpd_lock = threading.RLock()
    p._library_db_update = None
    p._library_poll_count = playermpd.LIBRARY_CHECK_POLLS
    p._was_updating_db = False
    return p


def published(publisher):
    return [c.args for c in publisher.send.call_args_list if c.args[0] == 'library.updated']


def test_first_poll_publishes_the_stamp(player, publisher):
    player._check_library_update(IDLE)

    assert published(publisher) == [('library.updated', {'db_update': 1000})]


def test_same_stamp_is_not_published_again(player, publisher):
    for _ in range(3 * playermpd.LIBRARY_CHECK_POLLS):
        player._check_library_update(IDLE)

    assert len(published(publisher)) == 1


def test_stats_are_checked_only_every_few_polls(player, publisher):
    player._check_library_update(IDLE)
    player.mpd_client.stats.reset_mock()

    for _ in range(playermpd.LIBRARY_CHECK_POLLS - 1):
        player._check_library_update(IDLE)
    player.mpd_client.stats.assert_not_called()

    player._check_library_update(IDLE)
    player.mpd_client.stats.assert_called_once()


def test_changed_stamp_is_published(player, publisher):
    player._check_library_update(IDLE)
    player.mpd_client.stats.return_value = {'db_update': '2000'}

    for _ in range(playermpd.LIBRARY_CHECK_POLLS):
        player._check_library_update(IDLE)

    assert published(publisher)[-1] == ('library.updated', {'db_update': 2000})


def test_finished_update_is_checked_at_once(player, publisher):
    player._check_library_update(IDLE)
    player._check_library_update(UPDATING)
    player.mpd_client.stats.return_value = {'db_update': '2000'}

    player._check_library_update(IDLE)

    assert published(publisher)[-1] == ('library.updated', {'db_update': 2000})


def test_mpd_not_reachable_publishes_nothing(player, publisher):
    player.mpd_client.stats.side_effect = OSError('no connection')

    player._check_library_update(IDLE)

    assert published(publisher) == []
