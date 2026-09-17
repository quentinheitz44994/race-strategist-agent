import math

import gpxpy
import numpy as np
from scipy.signal import savgol_filter

from app.core.models import RouteProfile, TrackPoint

EARTH_RADIUS_M = 6_371_000


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance en mètres entre deux points GPS, sur la sphère terrestre."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d_phi = p2 - p1
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def smooth_elevation(elevations: np.ndarray, window: int = 21, polyorder: int = 2) -> np.ndarray:
    """Lisse la série d'altitudes pour retirer le bruit du GPS."""
    n = len(elevations)
    if n < 5:
        return elevations
    window = min(window, n if n % 2 == 1 else n - 1)
    if window % 2 == 0:
        window -= 1
    if window <= polyorder:
        return elevations
    return savgol_filter(elevations, window, polyorder)


def compute_elevation_change(
    elevations: np.ndarray, threshold_m: float = 1.0
) -> tuple[float, float]:
    """Dénivelé positif et négatif cumulés, avec seuil de déclenchement."""
    gain = 0.0
    loss = 0.0
    reference = float(elevations[0])
    for value in elevations[1:]:
        delta = float(value) - reference
        if abs(delta) >= threshold_m:
            if delta > 0:
                gain += delta
            else:
                loss -= delta
            reference = float(value)
    return gain, loss


def load_route(source: str, name: str | None = None) -> RouteProfile:
    """Lit un fichier GPX et renvoie un parcours prêt à être segmenté."""
    with open(source, "r", encoding="utf-8") as handle:
        gpx = gpxpy.parse(handle)

    lats: list[float] = []
    lons: list[float] = []
    raw_elevations: list[float] = []

    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                if point.elevation is None:
                    continue
                lats.append(point.latitude)
                lons.append(point.longitude)
                raw_elevations.append(point.elevation)

    if len(lats) < 2:
        raise ValueError("Trace GPX vide ou sans altitude exploitable.")

    elevations = smooth_elevation(np.array(raw_elevations, dtype=float))

    distances = [0.0]
    for i in range(1, len(lats)):
        step = haversine_m(lats[i - 1], lons[i - 1], lats[i], lons[i])
        distances.append(distances[-1] + step)

    gain, loss = compute_elevation_change(elevations)

    points = [
        TrackPoint(lat=lats[i], lon=lons[i], elevation_m=float(elevations[i]), distance_m=distances[i])
        for i in range(len(lats))
    ]

    return RouteProfile(
        name=name or (gpx.tracks[0].name if gpx.tracks else None) or "parcours",
        distance_m=distances[-1],
        elev_gain_m=gain,
        elev_loss_m=loss,
        points=points,
    )