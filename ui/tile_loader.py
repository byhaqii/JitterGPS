"""Identified, cached, visible-tile-only OSM loading for Jitter GPS."""
import io
import json
import os
from pathlib import Path
import sys
import threading
import time

import requests
from PIL import Image, ImageTk
from tkintermapview import TkinterMapView

USER_AGENT = 'JitterGPS-Desktop/0.3 (desktop geolocation testing; local preview)'
TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
# OSM permits a fixed minimum-seven-day cache when cache headers aren't interpreted.
CACHE_SECONDS = 7 * 24 * 3600


class TileError(RuntimeError):
    pass


def default_cache_directory():
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Caches/JitterGPS/tiles-v1'
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.cache'))) / 'JitterGPS/tiles-v1'


class TileCache:
    def __init__(self, directory=None, *, get=None, clock=time.time):
        self.directory = Path(directory) if directory is not None else default_cache_directory()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.get = get or requests.get
        self.clock = clock
        self.lock = threading.Lock()
        self.retry_after = 0
        self.last_error = ''
        self.network_count = 0
        self.hit_count = 0

    @staticmethod
    def validate(data):
        with Image.open(io.BytesIO(data)) as image:
            if image.format != 'PNG' or image.size != (256, 256):
                raise TileError('Map provider returned an unexpected image.')
            image.verify()

    @staticmethod
    def _atomic_write(path, data):
        temporary = path.with_suffix(path.suffix + '.new')
        temporary.write_bytes(data)
        temporary.replace(path)

    def fetch(self, zoom, x, y, *, cancelled=None):
        if not (isinstance(zoom, int) and 0 <= zoom <= 19 and
                0 <= x < 2 ** zoom and 0 <= y < 2 ** zoom):
            raise TileError('Tile is outside map bounds.')
        # Serialize requests: duplicate visible tiles use the first result and a
        # blocked provider receives no parallel storm or automatic rapid retries.
        with self.lock:
            if cancelled is not None and cancelled():
                raise TileError("Map request cancelled.")
            now = self.clock()
            stem = self.directory / f'{zoom}-{x}-{y}'
            image_path, meta_path = stem.with_suffix('.png'), stem.with_suffix('.json')
            data, meta = None, {}
            try:
                data = image_path.read_bytes()
                self.validate(data)
                meta = json.loads(meta_path.read_text())
                if now - float(meta['saved']) < CACHE_SECONDS:
                    self.hit_count += 1
                    return data
            except (OSError, ValueError, KeyError, TypeError, TileError):
                data, meta = None, {}
            if now < self.retry_after:
                raise TileError(self.last_error)
            headers = {'User-Agent': USER_AGENT}
            if data is not None:
                if meta.get('etag'):
                    headers['If-None-Match'] = meta['etag']
                if meta.get('last_modified'):
                    headers['If-Modified-Since'] = meta['last_modified']
            try:
                self.network_count += 1
                response = self.get(TILE_URL.format(z=zoom, x=x, y=y), headers=headers, timeout=(3, 8))
                try:
                    response.raise_for_status()
                    if response.status_code == 304 and data is not None:
                        pass
                    elif response.status_code == 200:
                        data = response.content
                        self.validate(data)
                        meta = {'etag': response.headers.get('ETag'),
                                'last_modified': response.headers.get('Last-Modified')}
                        self._atomic_write(image_path, data)
                    else:
                        raise TileError(f'Unexpected tile status {response.status_code}')
                    meta['saved'] = now
                    self._atomic_write(meta_path, json.dumps(meta).encode())
                    return data
                finally:
                    response.close()
            except Exception as exc:
                status = getattr(locals().get('response'), 'status_code', None)
                self.last_error = (f'Map tiles unavailable ({status or "network/cache error"}). '
                                   'Provider requests paused; coordinate fields still work.')
                self.retry_after = now + (300 if status in (403, 429) else 30)
                raise TileError(self.last_error) from exc


class PolicyMapView(TkinterMapView):
    """Keep network/PIL work in loaders, create all Tk images on the UI thread."""
    def __init__(self, *args, on_tile_error=None, tile_cache=None, **kwargs):
        self.tile_cache = tile_cache or TileCache()
        self.on_tile_error = on_tile_error
        self.loaded_tile_count = 0
        self._reported_error = None
        super().__init__(*args, **kwargs)
        self.tile_server = TILE_URL

    def pre_cache(self):
        # Upstream prefetches rings outside the viewport. OSM disallows prefetch.
        return

    def request_image(self, zoom, x, y, db_cursor=None):
        if not self.running or self.use_database_only:
            return self.empty_tile_image
        try:
            data = self.tile_cache.fetch(zoom, x, y, cancelled=lambda: not self.running or zoom != round(self.zoom))
            with Image.open(io.BytesIO(data)) as image:
                return image.convert('RGB')
        except TileError as exc:
            message = str(exc)
            if message == "Map request cancelled." or not self.running:
                return self.empty_tile_image
            if self.on_tile_error is not None and message != self._reported_error:
                self._reported_error = message
                self.on_tile_error(message)  # callback must queue, never call Tk
            return self.empty_tile_image

    def update_canvas_tile_images(self):
        while self.image_load_queue_results and self.running:
            (zoom, x, y), tile, image = self.image_load_queue_results.pop(0)
            if zoom != round(self.zoom):
                continue
            if isinstance(image, Image.Image):
                image = ImageTk.PhotoImage(image, master=self)
                self.loaded_tile_count += 1
                self.tile_image_cache[f'{zoom}{x}{y}'] = image
                # Keep a bounded in-memory rendering cache; persistent tiles stay
                # on disk for their retention period even when evicted here.
                if len(self.tile_image_cache) > 512:
                    self.tile_image_cache.pop(next(iter(self.tile_image_cache)))
            tile.set_image(image)
        if self.running:
            self.after(10, self.update_canvas_tile_images)
