"""Manual developer integration check against a real isolated Chrome.
No external page or user's normal browser profile is used.
"""
import json
from contextlib import ExitStack
import http.server
import threading
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import requests
from websockets.sync.client import connect

from core.browser_finder import get_browser_executable
from core.cdp_client import CDPClient
from core.jitter_engine import JitterEngine, distance_m


def command(ws, ident, method, params=None):
    ws.send(json.dumps({'id': ident, 'method': method, 'params': params or {}}))
    while True:
        response = json.loads(ws.recv(timeout=10))
        if response.get('id') == ident:
            if 'error' in response:
                raise RuntimeError(response['error'])
            return response.get('result', {})


def verify():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body>Local GPS test</body></html>')

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = f'http://127.0.0.1:{server.server_port}'
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    scratch = Path.home() / '.hermes/profiles/builder/cache/scratch'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='jitter-check-', dir=scratch, ignore_cleanup_errors=True) as profile, ExitStack() as stack:
        proc = subprocess.Popen([get_browser_executable(), '--headless=new',
            f'--remote-debugging-port={port}', '--remote-debugging-address=127.0.0.1',
            f'--user-data-dir={profile}', '--no-first-run', '--no-default-browser-check',
            'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        client = CDPClient(port=port)
        try:
            base = f'http://127.0.0.1:{port}'
            for _ in range(100):
                try:
                    version = requests.get(base + '/json/version', timeout=.5).json()
                    break
                except requests.RequestException:
                    time.sleep(.1)
            else:
                raise RuntimeError('Chrome readiness timeout')
            browser = stack.enter_context(connect(version['webSocketDebuggerUrl']))
            command(browser, 1, 'Browser.grantPermissions', {'permissions': ['geolocation'], 'origin': origin})
            target = next(t for t in requests.get(base + '/json/list', timeout=3).json() if t['type'] == 'page')
            with connect(target['webSocketDebuggerUrl']) as page:
                command(page, 1, 'Page.navigate', {'url': origin})
                time.sleep(.5)
                print('Context:', command(page, 5, 'Runtime.evaluate', {'expression': 'JSON.stringify({url:location.href,secure:isSecureContext})', 'returnByValue': True}))
                print('Permission:', command(page, 6, 'Runtime.evaluate', {'expression': 'navigator.permissions.query({name:"geolocation"}).then(p=>p.state)', 'awaitPromise': True, 'returnByValue': True}))
                engine = JitterEngine()
                seen = set()
                for index in range(10):
                    lat, lng = engine.generate_unique_coord(-6.2088, 106.8456, 150)
                    count, errors = client.apply(lat, lng, accuracy=10)
                    assert count >= 1 and not errors, (count, errors)
                    # Verify browser's Geolocation API on a trustworthy origin via an isolated world.
                    result = command(page, 20 + index, 'Runtime.evaluate', {
                        'expression': 'new Promise(resolve => navigator.geolocation.getCurrentPosition(p => resolve({lat:p.coords.latitude,lng:p.coords.longitude}), e => resolve({error:e.message}), {timeout:3000,maximumAge:0}))',
                        'awaitPromise': True, 'returnByValue': True})
                    value = result.get('result', {}).get('value', {})
                    assert value.get('lat') == lat and value.get('lng') == lng, value
                    assert distance_m(-6.2088, 106.8456, lat, lng) <= 150
                    seen.add((lat, lng))
                assert len(seen) == 10
                count, errors = client.clear_geolocation_override()
                assert count >= 1 and not errors, (count, errors)
                print('PASS: 10 unique in-radius ticks read through navigator.geolocation; clear acknowledged.')
        finally:
            client.close()
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


if __name__ == '__main__':
    verify()
