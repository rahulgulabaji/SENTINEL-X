"""Geographic distance calculation.

Deliberately separate from app/inference/geometry.py: that module is 2D
pixel-plane geometry for YOLO zones/lines (point-in-polygon, segment
intersection on a video frame), not geographic coordinates -- a different
problem domain entirely, so this is a new module rather than an addition
to that one.

Pure function only -- no state, no I/O, no FastAPI/Pydantic dependency, so
it is trivially unit-testable and reusable from both the dispatch route and
tests.
"""

from __future__ import annotations

import math

_EARTH_RADIUS_KM = 6371.0088  # IUGG mean Earth radius, standard Haversine constant


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two (lat, lon) points in kilometers.

    Uses the Haversine formula -- NOT a naive subtraction of latitude and
    longitude, which is only valid very close to the equator and gets
    increasingly wrong as latitude increases (a degree of longitude shrinks
    toward the poles; the task this module backs explicitly requires real
    geographic distance, not a flat-plane approximation).
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return _EARTH_RADIUS_KM * c
