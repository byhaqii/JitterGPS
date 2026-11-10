import math
import unittest
from unittest.mock import patch

from core.jitter_engine import JitterEngine, distance_m


class JitterEngineTests(unittest.TestCase):
    def test_thousand_unique_rounded_points_within_radius(self):
        engine = JitterEngine()
        points = [engine.generate_unique_coord(-6.2, 106.8, 100) for _ in range(1000)]
        self.assertEqual(len(set(points)), 1000)
        self.assertEqual(len(engine.seen_coords), 1000)
        for lat, lng in points:
            self.assertEqual(lat, round(lat, 6))
            self.assertEqual(lng, round(lng, 6))
            self.assertLessEqual(distance_m(-6.2, 106.8, lat, lng), 100)

    def test_poles_and_antimeridian(self):
        engine = JitterEngine()
        for center in [(90, 180), (-90, -180), (0, 179.999999), (0, -179.999999)]:
            for _ in range(100):
                lat, lng = engine.generate_unique_coord(*center, 50000)
                self.assertTrue(-90 <= lat <= 90)
                self.assertTrue(-180 <= lng < 180)
                self.assertLessEqual(distance_m(*center, lat, lng), 50000)

    def test_invalid_nonfinite_and_out_of_range_inputs(self):
        engine = JitterEngine()
        for args in [(91, 0, 5), (-91, 0, 5), (0, 181, 5), (0, -181, 5),
                     (0, 0, 4.99), (0, 0, 50001), (math.nan, 0, 5),
                     (0, math.inf, 5), (0, 0, -math.inf)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                engine.generate_unique_coord(*args)

    def test_recent_history_bounded_at_fifty_thousand(self):
        engine = JitterEngine()
        first = engine.generate_unique_coord(0, 0, 50000)
        first_key = f'{first[0]:.6f},{first[1]:.6f}'
        for _ in range(50000):
            engine.generate_unique_coord(0, 0, 50000)
        self.assertEqual(len(engine.seen_coords), 50000)
        self.assertNotIn(first_key, engine.seen_coords)
        self.assertTrue(all(isinstance(key, str) for key in engine.seen_coords))

    def test_bounded_retry_exhaustion(self):
        engine = JitterEngine()
        with patch('core.jitter_engine.random.random', return_value=0):
            engine.generate_unique_coord(0, 0, 5)
            with self.assertRaisesRegex(RuntimeError, 'unique'):
                engine.generate_unique_coord(0, 0, 5)

    def test_signed_zero_cannot_bypass_uniqueness(self):
        engine = JitterEngine()
        engine.MAX_ATTEMPTS = 1
        with patch('core.jitter_engine.random.random', side_effect=[1e-20, 0, 1e-20, .5]):
            engine.generate_unique_coord(0, 0, 5)
            with self.assertRaises(RuntimeError):
                engine.generate_unique_coord(0, 0, 5)

    def test_known_great_circle_distance(self):
        self.assertAlmostEqual(distance_m(0, 0, 0, 1), 111195.0802335329, places=5)
        self.assertEqual(distance_m(90, 180, 90, 180), 0)


if __name__ == '__main__':
    unittest.main()
