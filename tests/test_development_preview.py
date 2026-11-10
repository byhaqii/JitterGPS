import tempfile
import unittest
from pathlib import Path
from dev import source_snapshot


class DevelopmentPreviewTests(unittest.TestCase):
    def test_tracks_only_application_python_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'ui').mkdir()
            (root / 'main.py').write_text('print(1)')
            (root / 'ui/app_window.py').write_text('x=1')
            first = source_snapshot(root)
            (root / 'ui/app_window.py').write_text('x=2')
            self.assertNotEqual(first, source_snapshot(root))
            second = source_snapshot(root)
            (root / 'README.md').write_text('docs')
            self.assertEqual(second, source_snapshot(root))


if __name__ == '__main__':
    unittest.main()
