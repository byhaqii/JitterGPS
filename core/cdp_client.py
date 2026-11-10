"""Synchronous page CDP sessions. Sites still require the user to click Allow.

No geolocation permission is granted automatically. Calls should be serialized
by the UI worker; one client owns its persistent page connections.
"""
import json
import math
import time

import requests
from websockets.sync.client import connect


class CDPClient:
    HTTP_TIMEOUT = 3
    RESPONSE_TIMEOUT = 3

    def __init__(self, port=9222):
        self.port = int(port)
        if not 1 <= self.port <= 65535:
            raise ValueError('Port must be 1..65535')
        self._connections = {}
        self._next_id = 0

    def _drop(self, url, errors):
        connection = self._connections.pop(url, None)
        if connection is not None:
            try:
                connection.close()
            except Exception as exc:
                errors.append(f'{url}: cleanup: {exc}')

    def _command(self, method, params):
        errors = []
        success = 0
        try:
            response = requests.get(f'http://127.0.0.1:{self.port}/json/list', timeout=self.HTTP_TIMEOUT)
            response.raise_for_status()
            targets = response.json()
            if not isinstance(targets, list):
                raise ValueError('Expected a page target list')
            urls = list(dict.fromkeys(t['webSocketDebuggerUrl'] for t in targets
                                     if t.get('type') == 'page' and t.get('webSocketDebuggerUrl')))
        except Exception as exc:
            errors.append(f'Target discovery: {exc}')
            for url in list(self._connections):
                self._drop(url, errors)
            return 0, errors
        for url in list(self._connections):
            if url not in urls:
                self._drop(url, errors)
        for url in urls:
            try:
                if url not in self._connections:
                    self._connections[url] = connect(url, open_timeout=self.HTTP_TIMEOUT, close_timeout=1)
                connection = self._connections[url]
                self._next_id += 1
                command_id = self._next_id
                connection.send(json.dumps({'id': command_id, 'method': method, 'params': params}))
                deadline = time.monotonic() + self.RESPONSE_TIMEOUT
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('CDP acknowledgement timed out')
                    reply = json.loads(connection.recv(timeout=remaining))
                    if reply.get('id') != command_id:
                        continue
                    if 'error' in reply:
                        raise RuntimeError(str(reply['error']))
                    if 'result' not in reply:
                        raise RuntimeError('CDP acknowledgement missing result')
                    success += 1
                    break
            except Exception as exc:
                errors.append(f'{url}: {exc}')
                self._drop(url, errors)
        return success, errors

    def apply(self, lat, lng, accuracy=10):
        """Set override on all current pages; return (acknowledged count, errors)."""
        lat, lng, accuracy = float(lat), float(lng), float(accuracy)
        if (not all(map(math.isfinite, (lat, lng, accuracy))) or
                not -90 <= lat <= 90 or not -180 <= lng <= 180 or accuracy < 0):
            raise ValueError('Invalid latitude, longitude or accuracy')
        return self._command('Emulation.setGeolocationOverride',
                             {'latitude': lat, 'longitude': lng, 'accuracy': accuracy})

    def clear_geolocation_override(self):
        """Clear all current page overrides; return (acknowledged count, errors)."""
        return self._command('Emulation.clearGeolocationOverride', {})

    def close(self):
        """Close all sockets and return cleanup error strings (empty on success)."""
        errors = []
        for url in list(self._connections):
            self._drop(url, errors)
        return errors
