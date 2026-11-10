"""Locate Chromium browsers and launch an isolated loopback CDP session."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import requests

_MAC = {
    'chrome': 'Google Chrome.app/Contents/MacOS/Google Chrome',
    'edge': 'Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    'brave': 'Brave Browser.app/Contents/MacOS/Brave Browser',
}
_WINDOWS = {
    'chrome': 'Google/Chrome/Application/chrome.exe',
    'edge': 'Microsoft/Edge/Application/msedge.exe',
    'brave': 'BraveSoftware/Brave-Browser/Application/brave.exe',
}


def get_browser_executable(preferred='chrome'):
    """Return preferred installed browser, falling back to Chrome/Edge/Brave."""
    if preferred not in _MAC:
        raise ValueError('Browser must be chrome, edge or brave')
    order = [preferred] + [name for name in _MAC if name != preferred]
    if sys.platform == 'darwin':
        roots, names = [Path('/Applications'), Path.home() / 'Applications'], _MAC
    elif sys.platform == 'win32':
        roots = [Path(os.environ.get('PROGRAMFILES', r'C:\Program Files')),
                 Path(os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)')),
                 Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local')))]
        names = _WINDOWS
    else:
        raise OSError('Supported platforms are macOS and Windows')
    for browser in order:
        for root in roots:
            candidate = root / names[browser]
            if candidate.is_file():
                return str(candidate)
    raise FileNotFoundError('Install Google Chrome, Microsoft Edge or Brave first')


def _profile_directory(browser_type, port):
    if sys.platform == 'darwin':
        root = Path.home() / 'Library/Application Support/JitterGPS'
    elif sys.platform == 'win32':
        root = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'JitterGPS'
    else:
        raise OSError('Supported platforms are macOS and Windows')
    profile = root / 'BrowserProfiles' / f'{browser_type}-{port}'
    profile.mkdir(parents=True, exist_ok=True)
    return profile


def launch_browser_with_cdp(port=9222, browser_type='chrome'):
    """Launch app-owned profile; return Popen only after CDP is ready.

    Never attach to an occupied port or reuse the user's default profile.
    Websites still require the user to click Allow for geolocation.
    """
    port = int(port)
    if not 1 <= port <= 65535:
        raise ValueError('Port must be 1..65535')
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.3)
        if probe.connect_ex(('127.0.0.1', port)) == 0:
            raise RuntimeError(f'Port {port} is already occupied; close that session or choose another port')
    # Binding also detects a bound but not yet listening port. Use a fresh
    # socket: macOS rejects bind() after a failed connect() with EINVAL.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
        try:
            reservation.bind(('127.0.0.1', port))
        except OSError as exc:
            raise RuntimeError(f'Port {port} is already occupied') from exc
    executable = get_browser_executable(browser_type)
    profile = _profile_directory(browser_type, port)
    process = subprocess.Popen([
        executable, f'--remote-debugging-port={port}',
        '--remote-debugging-address=127.0.0.1', f'--user-data-dir={profile}',
        '--no-first-run', '--no-default-browser-check', 'about:blank',
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + 10
    last_error = 'No CDP endpoint'
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f'Browser exited before CDP became ready (code {process.returncode})')
            try:
                response = requests.get(f'http://127.0.0.1:{port}/json/version', timeout=0.5)
                response.raise_for_status()
                if response.json().get('webSocketDebuggerUrl'):
                    return process
                last_error = 'CDP response missing browser WebSocket URL'
            except (requests.RequestException, ValueError, OSError) as exc:
                last_error = str(exc)
            time.sleep(0.1)
        raise TimeoutError(f'Browser CDP readiness timed out: {last_error}')
    except BaseException:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        raise
