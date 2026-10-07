"""
Deterministic geometry utilities for YOLO26 zone/line-crossing logic.

Pure functions only -- no model inference, no state, no I/O. Kept separate
from yolo26_service.py because zones/lines are reusable configuration
concepts, not YOLO-specific logic, and because it keeps that service file
from growing into an unnecessary 1000-line module.

Deliberately NOT a GIS library: just ray-casting point-in-polygon and
2D segment-intersection line crossing, which is all SENTINEL-X needs for
restricted areas / entrances / exits / parking zones.
"""

from __future__ import annotations

Point = tuple[float, float]


def point_in_polygon(point: Point, polygon: list[Point]) -> bool:
    """Standard ray-casting point-in-polygon test.

    `polygon` is a list of (x, y) vertices, open (no need to repeat the
    first point at the end). Returns False for a degenerate polygon
    (fewer than 3 vertices) rather than raising, since a mis-configured
    zone should just never match -- not crash a detection job.
    """
    if len(polygon) < 3:
        return False

    x, y = point
    n = len(polygon)
    inside = False

    x1, y1 = polygon[0]
    for i in range(1, n + 1):
        x2, y2 = polygon[i % n]
        if y1 != y2:
            # Edge crosses the horizontal ray at height y
            if min(y1, y2) < y <= max(y1, y2):
                x_intersect = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                if x < x_intersect:
                    inside = not inside
        x1, y1 = x2, y2

    return inside


def _orientation(a: Point, b: Point, c: Point) -> float:
    """Cross product of (b-a) x (c-a). Sign indicates turn direction."""
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(p: Point, q: Point, r: Point) -> bool:
    """True if q lies on segment p-r, given p, q, r are collinear."""
    return (
        min(p[0], r[0]) <= q[0] <= max(p[0], r[0])
        and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])
    )


def segments_intersect(p1: Point, p2: Point, p3: Point, p4: Point) -> bool:
    """Standard O(1) segment-intersection test (p1-p2 vs p3-p4), including
    collinear-overlap edge cases."""
    d1 = _orientation(p3, p4, p1)
    d2 = _orientation(p3, p4, p2)
    d3 = _orientation(p1, p2, p3)
    d4 = _orientation(p1, p2, p4)

    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and (
        (d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)
    ):
        return True

    if d1 == 0 and _on_segment(p3, p1, p4):
        return True
    if d2 == 0 and _on_segment(p3, p2, p4):
        return True
    if d3 == 0 and _on_segment(p1, p3, p2):
        return True
    if d4 == 0 and _on_segment(p1, p4, p2):
        return True

    return False


def line_crossing(prev_point: Point, curr_point: Point, line: list[Point]) -> bool:
    """True if the movement segment (prev_point -> curr_point) crosses the
    configured line segment. `line` must contain exactly 2 points; any other
    length is treated as mis-configured and never matches (fails safe, no
    crash)."""
    if len(line) != 2:
        return False
    return segments_intersect(prev_point, curr_point, line[0], line[1])
