"""
Simple HTTP interface to control the Phoniebox, e.g. from a widget on the home screen of a phone.

The core is otherwise only reachable via ZeroMQ, which apps like
[HTTP Shortcuts](https://http-shortcuts.rmy.ch/) or Tasker cannot talk to. This plugin starts a small
HTTP server (Python standard library, no extra dependencies) in a background thread and maps URLs to
RPC calls:

* ``/api/alias/<name>``: run an RPC command alias (``play_card``, ``toggle``, ``next_song``,
  ``change_volume``, ...), see ``components/rpc_command_alias.py``
* ``/api/rpc/<package>/<plugin>[/<method>]``: run any RPC call
* ``/api/status``: player status and volume

GET and POST are both accepted. Arguments are passed as query parameters ``args`` (a JSON list, or a single
value) and ``kwargs`` (a JSON object), or as JSON body ``{"args": [...], "kwargs": {...}}``.
All responses are JSON: ``{"result": ...}`` or ``{"error": "..."}``.

There is no authentication, just like the ZeroMQ ports of the RPC server: everyone in the local network
can control the box.

Configuration (``jukebox.yaml``, all optional)::

    http_api:
      enable: true
      host: 0.0.0.0
      port: 5559
"""

import json
import logging
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional, Tuple

import jukebox.cfghandler
import jukebox.plugs as plugs
import jukebox.utils
from components.rpc_command_alias import cmd_alias_definitions

logger = logging.getLogger('jb.http_api')
cfg = jukebox.cfghandler.get_handler('jukebox')

#: Largest accepted request body in bytes
MAX_BODY_SIZE = 64 * 1024

_server: Optional[ThreadingHTTPServer] = None
_thread: Optional[threading.Thread] = None


class HttpApiError(Exception):
    """A request that cannot be served, with the HTTP status code to answer with"""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def _decode_value(text: str) -> Any:
    """Decode a query parameter: JSON if possible, else the plain string"""
    try:
        return json.loads(text)
    except ValueError:
        return text


def parse_params(query: str = '', body: bytes = b'') -> Tuple[Optional[list], Optional[dict]]:
    """
    Get the arguments of a call from the query string and the request body

    :param query: Query string of the URL, e.g. ``args=[5]``
    :param body: Request body; if not empty it must be a JSON object with the keys ``args`` and / or ``kwargs``
    :return: ``(args, kwargs)``, each ``None`` if not given
    :raises HttpApiError: on invalid parameters (status 400)
    """
    args = None
    kwargs = None
    params = urllib.parse.parse_qs(query, keep_blank_values=True)
    unknown = set(params) - {'args', 'kwargs'}
    if unknown:
        raise HttpApiError(400, f"Unknown query parameters: {', '.join(sorted(unknown))}. Use 'args' and 'kwargs'.")
    if 'args' in params:
        args = _decode_value(params['args'][-1])
    if 'kwargs' in params:
        kwargs = _decode_value(params['kwargs'][-1])
    if body.strip():
        try:
            data = json.loads(body)
        except ValueError as e:
            raise HttpApiError(400, f"Request body is not valid JSON: {e}")
        if not isinstance(data, dict):
            raise HttpApiError(400, "Request body must be a JSON object with 'args' and / or 'kwargs'")
        args = data.get('args', args)
        kwargs = data.get('kwargs', kwargs)
    if args is not None and not isinstance(args, list):
        args = [args]
    if kwargs is not None and not isinstance(kwargs, dict):
        raise HttpApiError(400, "'kwargs' must be a JSON object")
    return args, kwargs


def parse_request(path: str, body: bytes = b'') -> Dict[str, Any]:
    """
    Translate the path of a request into an RPC call

    :param path: Path including query string, e.g. ``/api/alias/change_volume?args=[5]``
    :param body: Request body (JSON), see :func:`parse_params`
    :return: ``{'package', 'plugin', 'method', 'args', 'kwargs'}``, or ``{'status': True}`` for ``/api/status``
    :raises HttpApiError: for unknown paths (404) and invalid parameters (400)
    """
    url = urllib.parse.urlsplit(path)
    parts = [urllib.parse.unquote(p) for p in url.path.split('/') if p]
    if len(parts) < 2 or parts[0] != 'api':
        raise HttpApiError(404, f"Unknown path '{url.path}'. Use /api/alias/<name>, /api/rpc/... or /api/status")
    args, kwargs = parse_params(url.query, body)
    kind, rest = parts[1], parts[2:]

    if kind == 'status' and not rest:
        return {'status': True}

    if kind == 'alias' and len(rest) == 1:
        name = rest[0]
        if name not in cmd_alias_definitions:
            raise HttpApiError(404, f"Unknown alias '{name}'. Valid: {', '.join(sorted(cmd_alias_definitions))}")
        cmd = {'alias': name}
        if args is not None:
            cmd['args'] = args
        if kwargs is not None:
            cmd['kwargs'] = kwargs
        action = jukebox.utils.decode_rpc_command(cmd, logger)
        return {'package': action['package'], 'plugin': action['plugin'], 'method': action['method'],
                'args': action['args'], 'kwargs': action['kwargs']}

    if kind == 'rpc' and len(rest) in (2, 3):
        return {'package': rest[0], 'plugin': rest[1], 'method': rest[2] if len(rest) == 3 else None,
                'args': args, 'kwargs': kwargs}

    raise HttpApiError(404, f"Unknown path '{url.path}'. Use /api/alias/<name>, /api/rpc/... or /api/status")


def get_status() -> Dict[str, Any]:
    """Player status (MPD status plus current song) and volume, for ``/api/status``"""
    status = dict(plugs.call('player', 'ctrl', 'playerstatus') or {})
    try:
        status['volume'] = plugs.call('volume', 'ctrl', 'get_volume')
    except Exception as e:
        logger.debug(f"No volume for status: {e}")
    return status


def execute(call: Dict[str, Any]) -> Any:
    """Run a call returned by :func:`parse_request` and return its result"""
    if call.get('status'):
        return get_status()
    if not plugs.exists(call['package'], call['plugin'], call['method']):
        name = '.'.join(p for p in (call['package'], call['plugin'], call['method']) if p)
        raise HttpApiError(404, f"Unknown RPC call '{name}'")
    try:
        return plugs.call(call['package'], call['plugin'], call['method'],
                          args=call['args'] or (), kwargs=call['kwargs'] or {})
    except TypeError as e:
        # Mostly wrong or missing arguments
        raise HttpApiError(400, f"{e.__class__.__name__}: {e}")
    except Exception as e:
        raise HttpApiError(500, f"{e.__class__.__name__}: {e}")


class _RequestHandler(BaseHTTPRequestHandler):
    server_version = 'PhonieboxHttpApi'

    def _send_json(self, status: int, data: Dict[str, Any]):
        payload = json.dumps(data, default=str).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(payload)

    def _handle(self, body: bytes = b''):
        try:
            call = parse_request(self.path, body)
            result = execute(call)
        except HttpApiError as e:
            logger.warning(f"{self.command} {self.path}: {e.status} {e}")
            self._send_json(e.status, {'error': str(e)})
            return
        except Exception as e:
            logger.exception(f"{self.command} {self.path}: unexpected error")
            self._send_json(500, {'error': f"{e.__class__.__name__}: {e}"})
            return
        self._send_json(200, {'result': result})

    def do_GET(self):  # noqa: N802 (name given by BaseHTTPRequestHandler)
        self._handle()

    def do_POST(self):  # noqa: N802
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY_SIZE:
            self._send_json(413 if length > 0 else 400, {'error': 'Invalid or too large request body'})
            return
        self._handle(self.rfile.read(length) if length else b'')

    def log_message(self, format, *args):  # noqa: A002 (signature of BaseHTTPRequestHandler)
        logger.debug(f"{self.address_string()} {format % args}")


@plugs.initialize
def initialize():
    global _server, _thread
    if not cfg.setndefault('http_api', 'enable', value=True):
        logger.info("HTTP API disabled (http_api.enable)")
        return
    host = cfg.setndefault('http_api', 'host', value='0.0.0.0')
    port = int(cfg.setndefault('http_api', 'port', value=5559))
    try:
        _server = ThreadingHTTPServer((host, port), _RequestHandler)
    except OSError as e:
        logger.error(f"Cannot start HTTP API on {host}:{port}: {e}")
        _server = None
        return
    _server.daemon_threads = True
    _thread = threading.Thread(target=_server.serve_forever, name='HttpApi', daemon=True)
    _thread.start()
    logger.info(f"HTTP API listening on {host}:{port}")


@plugs.register
def get_address() -> Optional[Dict[str, Any]]:
    """Host and port the HTTP API listens on, or None if it is not running"""
    if _server is None:
        return None
    host, port = _server.server_address[:2]
    return {'host': host, 'port': port}


@plugs.atexit
def atexit(**ignored_kwargs):
    global _server
    if _server is not None:
        _server.shutdown()
        _server.server_close()
        _server = None
