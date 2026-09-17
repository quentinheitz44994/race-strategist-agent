from app.core.gpx import compute_elevation_change
from app.core.models import RouteProfile, Segment

import numpy as np


def _classify(avg_slope: float) -> str:
    if avg_slope >= 0.03:
        return "montée"
    if avg_slope <= -0.03:
        return "descente"
    return "plat"


def _build_segment(index: int, points: list) -> Segment:
    elevations = np.array([p.elevation_m for p in points], dtype=float)
    start_m = points[0].distance_m
    end_m = points[-1].distance_m
    distance = end_m - start_m
    gain, loss = compute_elevation_change(elevations)
    avg_slope = (elevations[-1] - elevations[0]) / distance if distance > 0 else 0.0

    return Segment(
        index=index,
        start_m=start_m,
        end_m=end_m,
        distance_m=distance,
        elev_gain_m=gain,
        elev_loss_m=loss,
        avg_slope=float(avg_slope),
        alt_min_m=float(elevations.min()),
        alt_max_m=float(elevations.max()),
        kind=_classify(float(avg_slope)),
    )


def segment_route(route: RouteProfile, target_segments: int = 15) -> list[Segment]:
    """Découpe le parcours en tronçons de longueur régulière."""
    if target_segments < 1:
        raise ValueError("target_segments doit être au moins 1.")

    step = route.distance_m / target_segments
    segments: list[Segment] = []
    start_index = 0

    for i, point in enumerate(route.points):
        is_last = i == len(route.points) - 1
        long_enough = point.distance_m - route.points[start_index].distance_m >= step
        if (long_enough or is_last) and i > start_index:
            segments.append(_build_segment(len(segments), route.points[start_index : i + 1]))
            start_index = i

    return segments