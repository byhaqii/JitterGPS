"""Strict pasted coordinates and spherical radius preview geometry."""
import math

from core.jitter_engine import EARTH_RADIUS_M


def validate_center(lat, lng):
    lat, lng = float(lat), float(lng)
    if not all(map(math.isfinite, (lat, lng))):
        raise ValueError('Coordinates must be finite numbers.')
    if not -90 <= lat <= 90 or not -180 <= lng <= 180:
        raise ValueError('Use latitude -90…90, longitude -180…180 (in that order).')
    return lat, lng


def radius_polygon(lat, lng, radius, segments=72):
    """Closed geodesic circle, including well-defined destinations at the poles."""
    lat, lng = validate_center(lat, lng)
    radius = float(radius)
    if not math.isfinite(radius) or not 5 <= radius <= 50000:
        raise ValueError('Radius must be between 5 and 50000 meters.')
    phi, lam = math.radians(lat), math.radians(lng)
    arc = radius / EARTH_RADIUS_M
    points = []
    for index in range(segments):
        bearing = 2 * math.pi * index / segments
        x = (math.cos(arc) * math.cos(phi) * math.cos(lam)
             + math.sin(arc) * (-math.cos(bearing) * math.sin(phi) * math.cos(lam)
                               - math.sin(bearing) * math.sin(lam)))
        y = (math.cos(arc) * math.cos(phi) * math.sin(lam)
             + math.sin(arc) * (-math.cos(bearing) * math.sin(phi) * math.sin(lam)
                               + math.sin(bearing) * math.cos(lam)))
        z = math.cos(arc) * math.sin(phi) + math.sin(arc) * math.cos(bearing) * math.cos(phi)
        points.append((math.degrees(math.atan2(z, math.hypot(x, y))),
                       (math.degrees(math.atan2(y, x)) + 180) % 360 - 180))
    return points + [points[0]]


def parse_coordinate_pair(text):
    parts = text.strip().split(',')
    if len(parts) != 2:
        raise ValueError('Paste exactly latitude, longitude (for example -6.881776, 107.610926).')
    try:
        return validate_center(*parts)
    except (ValueError, TypeError) as exc:
        raise ValueError(f'Invalid coordinate pair. {exc}') from exc
