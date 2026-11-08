# RPi-Jukebox-RFID Version 3
# Copyright (c) See file LICENSE in project root folder
"""Tests for the HTTP API (http_api): request parsing, execution and the HTTP server (plugs mocked)"""
import json
import os
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

import pytest

# In case this is run locally from
sys.path.append(os.path.abspath('../../src/jukebox'))
import jukebox.plugs as plugs  # noqa: E402

plugs.ALLOW_DIRECT_IMPORTS = True
import components.http_api as http_api  # noqa: E402
from components.http_api import HttpApiError  # noqa: E402


# ---------------------------------------------------------------------------
# parse_params / parse_request
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('query, body, expected', [
    ('', b'', (None, None)),
    ('args=[5]', b'', ([5], None)),
    ('args=5', b'', ([5], None)),
    ('args=Kinderlieder', b'', (['Kinderlieder'], None)),
    ('args=%5B%222024%22%5D', b'', (['2024'], None)),
    ('kwargs={"folder":"a/b","recursive":true}', b'', (None, {'folder': 'a/b', 'recursive': True})),
    ('', b'{"args": ["x"], "kwargs": {"y": 1}}', (['x'], {'y': 1})),
    ('args=[1]', b'{"kwargs": {"y": 1}}', ([1], {'y': 1})),
    ('', b'  ', (None, None)),
])
def test_parse_params(query, body, expected):
    assert http_api.parse_params(query, body) == expected


@pytest.mark.parametrize('query, body', [
    ('folder=x', b''),
    ('kwargs=[1]', b''),
    ('', b'not json'),
    ('', b'[1, 2]'),
])
def test_parse_params_invalid(query, body):
    with pytest.raises(HttpApiError) as e:
        http_api.parse_params(query, body)
    assert e.value.status == 400


def test_parse_request_alias():
    call = http_api.parse_request('/api/alias/toggle')
    assert call == {'package': 'player', 'plugin': 'ctrl', 'method': 'toggle', 'args': None, 'kwargs': None}


def test_parse_request_alias_with_args():
    call = http_api.parse_request('/api/alias/change_volume?args=[-5]')
    assert call == {'package': 'volume', 'plugin': 'ctrl', 'method': 'change_volume', 'args': [-5], 'kwargs': None}


def test_parse_request_alias_does_not_change_definitions():
    http_api.parse_request('/api/alias/play_card?args=["x"]')
    assert 'args' not in http_api.cmd_alias_definitions['play_card']


def test_parse_request_rpc():
    assert http_api.parse_request('/api/rpc/player/ctrl/play_folder/?kwargs={"folder":"Hörspiele"}') == {
        'package': 'player', 'plugin': 'ctrl', 'method': 'play_folder', 'args': None,
        'kwargs': {'folder': 'Hörspiele'}}
    assert http_api.parse_request('/api/rpc/misc/get_start_time') == {
        'package': 'misc', 'plugin': 'get_start_time', 'method': None, 'args': None, 'kwargs': None}


def test_parse_request_quoted_path():
    call = http_api.parse_request('/api/rpc/player/ctrl/play%5Ffolder')
    assert call['method'] == 'play_folder'


def test_parse_request_status():
    assert http_api.parse_request('/api/status') == {'status': True}


@pytest.mark.parametrize('path', [
    '/', '/api', '/api/', '/foo/alias/toggle', '/api/alias', '/api/alias/does_not_exist',
    '/api/alias/toggle/extra', '/api/rpc/player', '/api/rpc/a/b/c/d', '/api/status/x', '/api/other',
])
def test_parse_request_unknown(path):
    with pytest.raises(HttpApiError) as e:
        http_api.parse_request(path)
    assert e.value.status == 404


# ---------------------------------------------------------------------------
# execute
# ---------------------------------------------------------------------------

CALL = {'package': 'player', 'plugin': 'ctrl', 'method': 'toggle', 'args': None, 'kwargs': None}


def test_execute_calls_plug():
    with mock.patch.object(plugs, 'exists', return_value=True), \
            mock.patch.object(plugs, 'call', return_value='ok') as call:
        assert http_api.execute(CALL) == 'ok'
    call.assert_called_once_with('player', 'ctrl', 'toggle', args=(), kwargs={})


def test_execute_passes_arguments():
    c = dict(CALL, args=[1], kwargs={'a': 2})
    with mock.patch.object(plugs, 'exists', return_value=True), mock.patch.object(plugs, 'call') as call:
        http_api.execute(c)
    call.assert_called_once_with('player', 'ctrl', 'toggle', args=[1], kwargs={'a': 2})


def test_execute_unknown_plug():
    with mock.patch.object(plugs, 'exists', return_value=False), mock.patch.object(plugs, 'call') as call:
        with pytest.raises(HttpApiError) as e:
            http_api.execute(CALL)
    assert e.value.status == 404
    assert 'player.ctrl.toggle' in str(e.value)
    call.assert_not_called()


@pytest.mark.parametrize('error, status', [(TypeError('missing argument'), 400), (RuntimeError('mpd down'), 500)])
def test_execute_errors(error, status):
    with mock.patch.object(plugs, 'exists', return_value=True), mock.patch.object(plugs, 'call', side_effect=error):
        with pytest.raises(HttpApiError) as e:
            http_api.execute(CALL)
    assert e.value.status == status
    assert str(error) in str(e.value)


def test_execute_status():
    def fake_call(package, plugin, method=None, **kwargs):
        if package == 'player':
            return {'state': 'play', 'title': 'Song'}
        return 42

    with mock.patch.object(plugs, 'call', side_effect=fake_call):
        assert http_api.execute({'status': True}) == {'state': 'play', 'title': 'Song', 'volume': 42}


def test_status_without_volume():
    def fake_call(package, plugin, method=None, **kwargs):
        if package == 'player':
            return {'state': 'stop'}
        raise KeyError('volume')

    with mock.patch.object(plugs, 'call', side_effect=fake_call):
        assert http_api.get_status() == {'state': 'stop'}


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------

@pytest.fixture
def server():
    srv = ThreadingHTTPServer(('127.0.0.1', 0), http_api._RequestHandler)
    srv.daemon_threads = True
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{srv.server_address[1]}'
    srv.shutdown()
    srv.server_close()


def _request(url, data=None):
    req = urllib.request.Request(url, data=data, method='POST' if data is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_server_get(server):
    with mock.patch.object(plugs, 'exists', return_value=True), \
            mock.patch.object(plugs, 'call', return_value={'volume': 30}) as call:
        assert _request(server + '/api/alias/change_volume?args=[5]') == (200, {'result': {'volume': 30}})
    call.assert_called_once_with('volume', 'ctrl', 'change_volume', args=[5], kwargs={})


def test_server_post_body(server):
    with mock.patch.object(plugs, 'exists', return_value=True), \
            mock.patch.object(plugs, 'call', return_value=None) as call:
        status, data = _request(server + '/api/rpc/player/ctrl/play_folder',
                                data=json.dumps({'kwargs': {'folder': 'x'}}).encode())
    assert (status, data) == (200, {'result': None})
    call.assert_called_once_with('player', 'ctrl', 'play_folder', args=(), kwargs={'folder': 'x'})


def test_server_post_without_body(server):
    with mock.patch.object(plugs, 'exists', return_value=True), mock.patch.object(plugs, 'call', return_value=1):
        assert _request(server + '/api/alias/toggle', data=b'') == (200, {'result': 1})


def test_server_not_found(server):
    status, data = _request(server + '/api/alias/does_not_exist')
    assert status == 404
    assert 'does_not_exist' in data['error']


def test_server_error(server):
    with mock.patch.object(plugs, 'exists', return_value=True), \
            mock.patch.object(plugs, 'call', side_effect=RuntimeError('boom')):
        status, data = _request(server + '/api/alias/toggle')
    assert status == 500
    assert data == {'error': 'RuntimeError: boom'}


def test_server_result_not_json(server):
    with mock.patch.object(plugs, 'exists', return_value=True), mock.patch.object(plugs, 'call', return_value={1, 2}):
        status, data = _request(server + '/api/alias/toggle')
    assert status == 200
    assert data['result'] == str({1, 2})
