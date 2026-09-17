from dataclasses import dataclass
from datetime import datetime

import gpxpy
import numpy as np

from app.core.gpx import haversine_m, smooth_elevation


@dataclass
class ActivityPoint:
    """Un point d'activité réelle : position, altitude, et horodatage."""

    lat: float
    lon: float
    elevation_m: float
    time: datetime


def load_activity_gpx(path: str) -> list[ActivityPoint]:
    """Lit un .gpx d'activité réelle, horodatage inclus (contrairement à load_route)."""
    with open(path, "r", encoding="utf-8") as handle:
        gpx = gpxpy.parse(handle)

    points: list[ActivityPoint] = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                if point.elevation is None or point.time is None:
                    continue
                points.append(
                    ActivityPoint(
                        lat=point.latitude,
                        lon=point.longitude,
                        elevation_m=point.elevation,
                        time=point.time,
                    )
                )

    if len(points) < 2:
        raise ValueError(f"Activité vide ou sans horodatage exploitable : {path}")

    return points

MIN_SEGMENT_DISTANCE_M = 20.0
MIN_SEGMENT_DURATION_S = 5.0
MAX_PLAUSIBLE_SPEED_M_S = 6.0


def extract_slope_speed_pairs(points: list[ActivityPoint]) -> list[tuple[float, float]]:
    """Découpe l'activité en petits pas et renvoie (pente, vitesse) pour chacun.

    Les pas trop courts en distance ou en temps sont ignorés : le bruit GPS y domine
    largement le signal (une pente ou une vitesse calculée sur 3 m n'importe quoi).
    """
    elevations = smooth_elevation(
        np.array([p.elevation_m for p in points], dtype=float)
    )

    pairs: list[tuple[float, float]] = []
    start = 0

    for i in range(1, len(points)):
        distance = haversine_m(
            points[start].lat, points[start].lon, points[i].lat, points[i].lon
        )
        duration = (points[i].time - points[start].time).total_seconds()

        if distance < MIN_SEGMENT_DISTANCE_M or duration < MIN_SEGMENT_DURATION_S:
            continue

        slope = (elevations[i] - elevations[start]) / distance
        speed = distance / duration

        if 0 < speed <= MAX_PLAUSIBLE_SPEED_M_S:
            pairs.append((slope, speed))

        start = i

    return pairs
