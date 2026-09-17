import math

import pytest

from app.core.models import RouteProfile, TrackPoint
from app.core.segmentation import segment_route


def route_synthetique(n_points: int = 1000, longueur_m: float = 10_000.0) -> RouteProfile:
    """Un parcours en forme de vague : deux montées et deux descentes franches."""
    points = []
    for i in range(n_points):
        d = longueur_m * i / (n_points - 1)
        elevation = 100.0 + 80.0 * math.sin(4 * math.pi * d / longueur_m)
        points.append(TrackPoint(lat=48.0, lon=2.0, elevation_m=elevation, distance_m=d))
    return RouteProfile(
        name="synthetique",
        distance_m=longueur_m,
        elev_gain_m=0.0,
        elev_loss_m=0.0,
        points=points,
    )


def test_nombre_de_segments_dans_les_clous():
    segments = segment_route(route_synthetique(), target_segments=15)
    assert 10 <= len(segments) <= 25


def test_segments_contigus_et_couvrants():
    route = route_synthetique()
    segments = segment_route(route)

    assert segments[0].start_m == pytest.approx(0.0)
    assert segments[-1].end_m == pytest.approx(route.distance_m)

    for precedent, suivant in zip(segments, segments[1:]):
        assert precedent.end_m == pytest.approx(suivant.start_m)


def test_somme_des_distances_egale_le_total():
    route = route_synthetique()
    total = sum(s.distance_m for s in segment_route(route))
    assert total == pytest.approx(route.distance_m)


def test_classification_coherente():
    for s in segment_route(route_synthetique()):
        if s.kind == "montée":
            assert s.avg_slope > 0
        elif s.kind == "descente":
            assert s.avg_slope < 0