"""Contrast and sizing contracts for the native workbench."""
import importlib.util
import pathlib
import unittest


class ThemeTests(unittest.TestCase):
    def test_geographic_outline_stays_visible_on_light_map(self):
        from ui import theme
        self.assertTrue(hasattr(theme, 'MAP_OUTLINE'), 'separate light-map signal is missing')
        self.assertGreaterEqual(theme.contrast(theme.MAP_OUTLINE, '#f2efe9'), 3)

    def test_theme_has_accessible_semantic_pairs(self):
        path = pathlib.Path(__file__).resolve().parents[1] / 'ui/theme.py'
        self.assertTrue(path.exists(), 'native workbench theme is missing')
        spec = importlib.util.spec_from_file_location('theme', path)
        theme = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(theme)
        for foreground, background in theme.TEXT_PAIRS:
            self.assertGreaterEqual(theme.contrast(foreground, background), 4.5)
        for foreground, background in theme.EDGE_PAIRS:
            self.assertGreaterEqual(theme.contrast(foreground, background), 3)
        self.assertEqual(theme.RAIL_WIDTH, 300)
        self.assertEqual(theme.CONTROL_HEIGHT, 40)
        self.assertEqual(theme.ACTIVITY_HEIGHT, 120)


if __name__ == '__main__':
    unittest.main()
