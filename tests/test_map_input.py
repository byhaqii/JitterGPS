import unittest

from ui import coordinate_input


class CoordinateInputTests(unittest.TestCase):
    def test_pasted_pair(self):
        self.assertEqual(coordinate_input.parse_coordinate_pair('-6.881776, 107.610926'), (-6.881776, 107.610926))
        self.assertEqual(coordinate_input.parse_coordinate_pair(' \n -45.5 , -123.25 \t'), (-45.5, -123.25))
        self.assertEqual(coordinate_input.parse_coordinate_pair('90, -180'), (90, -180))
        for text in ('', '1', '1 2', '1,2,3', 'latitude, longitude', 'nan,1', '1,inf', '-inf,2', '91,0', '0,-181', '107.610926,-6.881776'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                coordinate_input.parse_coordinate_pair(text)

    def test_radius_polygon_geodesic_distances(self):
        from core.jitter_engine import distance_m
        for center in ((-6.881776, 107.610926), (0, 179.9999), (89.99, -179.99), (90, 0), (-90, 180)):
            for radius in (5, 150, 50000):
                points = coordinate_input.radius_polygon(*center, radius)
                self.assertEqual(len(points), 73)
                self.assertEqual(points[0], points[-1])
                for lat, lng in points:
                    self.assertTrue(-90 <= lat <= 90)
                    self.assertTrue(-180 <= lng <= 180)
                    self.assertAlmostEqual(distance_m(*center, lat, lng), radius, delta=0.001)
        for radius in (0, 4, 50001, float('nan')):
            with self.assertRaises(ValueError):
                coordinate_input.radius_polygon(0, 0, radius)


if __name__ == '__main__':
    unittest.main()
