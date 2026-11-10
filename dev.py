"""Open a source preview and restart after valid source changes.
Close the preview window to stop watching. Restarts request normal GUI cleanup.
"""
import hashlib
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def source_snapshot(root):
    paths = [root / 'main.py']
    for folder in ('ui', 'core'):
        paths.extend((root / folder).glob('*.py'))
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths if p.is_file()}


def valid_sources(snapshot):
    try:
        for name in snapshot:
            compile(Path(name).read_text(), name, 'exec')
    except (SyntaxError, OSError) as exc:
        print(f'Waiting for a valid save: {exc}', flush=True)
        return False
    return True


def run():
    root = Path(__file__).resolve().parent
    env = {**os.environ, 'JITTER_LIVE_PREVIEW': '1'}
    stopping = False
    def stop(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    def launch():
        print('Opening Jitter GPS live preview', flush=True)
        return subprocess.Popen([sys.executable, '-u', str(root / 'main.py')], cwd=root, env=env)
    current = source_snapshot(root)
    child = launch()
    try:
        while not stopping:
            time.sleep(.5)
            if child.poll() is not None:
                print('Preview closed. Watcher stopped.', flush=True)
                break
            updated = source_snapshot(root)
            if updated == current:
                continue
            time.sleep(1)
            updated = source_snapshot(root)
            if not valid_sources(updated):
                continue
            print('Saved changes found; requesting cleanup before restart…', flush=True)
            child.terminate()
            try:
                child.wait(timeout=45)
            except subprocess.TimeoutExpired:
                print('Cleanup still running; not forcing exit or opening another instance.', flush=True)
                break
            current = updated
            if not stopping:
                child = launch()
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=45)
            except subprocess.TimeoutExpired:
                print('Preview remains open to finish cleanup.', flush=True)


if __name__ == '__main__':
    run()
