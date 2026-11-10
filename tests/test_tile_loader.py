import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from PIL import Image
import requests

from ui.tile_loader import TileCache, TileError, USER_AGENT, CACHE_SECONDS


def tile_response(status=200):
    data = io.BytesIO()
    Image.new('RGB', (256, 256), '#7db273').save(data, 'PNG')
    response = Mock(status_code=status, content=data.getvalue(), headers={'ETag': 'tile-v1'})
    if status >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(str(status))
    return response


class TileLoaderTests(unittest.TestCase):
    def test_app_identification_and_persistent_seven_day_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            get = Mock(return_value=tile_response())
            cache = TileCache(Path(folder), get=get)
            first = cache.fetch(15, 26178, 17011)
            self.assertEqual(Image.open(io.BytesIO(first)).size, (256, 256))
            args, kwargs = get.call_args
            self.assertEqual(args[0], 'https://tile.openstreetmap.org/15/26178/17011.png')
            self.assertEqual(kwargs['headers']['User-Agent'], USER_AGENT)
            self.assertIn('JitterGPS', USER_AGENT)
            self.assertIn('timeout', kwargs)
            self.assertGreaterEqual(CACHE_SECONDS, 7 * 24 * 3600)
            second = TileCache(Path(folder), get=get).fetch(15, 26178, 17011)
            self.assertEqual(first, second)
            self.assertEqual(get.call_count, 1)

    def test_blocked_tiles_not_cached_and_no_request_storm(self):
        with tempfile.TemporaryDirectory() as folder:
            get = Mock(return_value=tile_response(403))
            cache = TileCache(Path(folder), get=get)
            for x in (10, 11):
                with self.assertRaises(TileError):
                    cache.fetch(5, x, 12)
            self.assertEqual(get.call_count, 1)
            self.assertEqual(list(Path(folder).glob('*.png')), [])

    def test_expired_cache_conditionally_revalidated(self):
        with tempfile.TemporaryDirectory() as folder:
            get = Mock(side_effect=[tile_response(), tile_response(304)])
            clock = Mock(return_value=1000)
            cache = TileCache(Path(folder), get=get, clock=clock)
            data = cache.fetch(3, 2, 1)
            clock.return_value += CACHE_SECONDS + 1
            self.assertEqual(cache.fetch(3, 2, 1), data)
            self.assertEqual(get.call_args.kwargs['headers']['If-None-Match'], 'tile-v1')

    def test_cancelled_worker_makes_no_network_request(self):
        with tempfile.TemporaryDirectory() as folder:
            get = Mock(return_value=tile_response())
            cache = TileCache(Path(folder), get=get)
            with self.assertRaises(TileError):
                cache.fetch(3, 2, 1, cancelled=lambda: True)
            get.assert_not_called()

    def test_invalid_image_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            response = tile_response()
            response.content = b'not an image'
            cache = TileCache(Path(folder), get=Mock(return_value=response))
            with self.assertRaises(TileError):
                cache.fetch(3, 2, 1)


if __name__ == '__main__':
    unittest.main()
