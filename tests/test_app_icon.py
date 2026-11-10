import unittest
from pathlib import Path
from PIL import Image


class AppIconTests(unittest.TestCase):
    def test_icon_assets_are_valid_and_transparent(self):
        assets = Path(__file__).resolve().parents[1] / 'assets'
        for suffix, size in [('png', (1024, 1024)), ('icns', (1024, 1024)), ('ico', (256, 256))]:
            path = assets / f'JitterGPS.{suffix}'
            self.assertTrue(path.is_file(), f'Missing {path.name}')
            with Image.open(path) as image:
                self.assertEqual(image.size, size)
                image.load()
                self.assertEqual(image.convert('RGBA').getpixel((0, 0))[3], 0)


if __name__ == '__main__':
    unittest.main()
