"""Spherical, rounded GPS jitter with bounded recent-coordinate history."""
import math
import random
from collections import deque

EARTH_RADIUS_M = 6371008.8


def distance_m(lat1, lng1, lat2, lng2):
    """Return spherical great-circle distance in meters (haversine)."""
    a, b = math.radians(lat1), math.radians(lat2)
    dlat, dlng = b - a, math.radians(lng2 - lng1)
    h = math.sin(dlat / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(min(1.0, max(0.0, h))))


class JitterEngine:
    MAX_SEEN = 50000
    MAX_ATTEMPTS = 1000

    def __init__(self):
        self.seen_coords = set()
        self._recent = deque()

    def generate_unique_coord(self, lat, lng, radius):
        """Return a six-decimal coordinate inside radius; raise on exhaustion."""
        lat, lng, radius = float(lat), float(lng), float(radius)
        if not all(map(math.isfinite, (lat, lng, radius))):
            raise ValueError('Latitude, longitude and radius must be finite')
        if not -90 <= lat <= 90 or not -180 <= lng <= 180:
            raise ValueError('Latitude must be -90..90; longitude must be -180..180')
        if not 5 <= radius <= 50000:
            raise ValueError('Radius must be 5..50000 meters')
        phi, lam = math.radians(lat), math.radians(lng)
        for _ in range(self.MAX_ATTEMPTS):
            arc = radius * math.sqrt(random.random()) / EARTH_RADIUS_M
            bearing = 2 * math.pi * random.random()
            # Use a local orthonormal basis instead of the usual longitude
            # division: this remains well-defined at the exact poles.
            x = (math.cos(arc) * math.cos(phi) * math.cos(lam)
                 + math.sin(arc) * (-math.cos(bearing) * math.sin(phi) * math.cos(lam)
                                   - math.sin(bearing) * math.sin(lam)))
            y = (math.cos(arc) * math.cos(phi) * math.sin(lam)
                 + math.sin(arc) * (-math.cos(bearing) * math.sin(phi) * math.sin(lam)
                                   + math.sin(bearing) * math.cos(lam)))
            z = math.cos(arc) * math.sin(phi) + math.sin(arc) * math.cos(bearing) * math.cos(phi)
            out_lat = round(math.degrees(math.atan2(z, math.hypot(x, y))), 6)
            out_lng = round((math.degrees(math.atan2(y, x)) + 180) % 360 - 180, 6)
            if out_lng == 180:
                out_lng = -180.0
            # Canonicalize signed zero so float-equal pairs cannot be repeated.
            out_lat = 0.0 if out_lat == 0 else out_lat
            out_lng = 0.0 if out_lng == 0 else out_lng
            key = f'{out_lat:.6f},{out_lng:.6f}'
            if key in self.seen_coords or distance_m(lat, lng, out_lat, out_lng) > radius:
                continue
            self.seen_coords.add(key)
            self._recent.append(key)
            if len(self._recent) > self.MAX_SEEN:
                self.seen_coords.discard(self._recent.popleft())
            return out_lat, out_lng
        raise RuntimeError('Unable to find a unique rounded coordinate within radius after bounded retries')
