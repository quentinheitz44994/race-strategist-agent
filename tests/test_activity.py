from datetime import datetime, timedelta

import pytest

from app.core.activity import ActivityPoint, extract_slope_speed_pairs


def _fabrique_activite(vitesse_m_s: float, pente: float, n_points: int = 50) -> list[ActivityPoint]:
    """Simule une activité rectiligne à vitesse et pente constantes, plein nord."""
    debut = datetime(2026, 6, 1, 8, 0, 0)
    lat0, lon0 = 43.5, 11.3
    metres_par_degre_lat = 111_320.0

    points = []
    for i in range(n_points):
        t = i * 2.0  # un point toutes les 2 secondes
        distance = vitesse_m_s * t
        points.append(
            ActivityPoint(
                lat=lat0 + (distance / metres_par_degre_lat),
                lon=lon0,
                elevation_m=100.0 + pente * distance,
                time=debut + timedelta(seconds=t),
            )
        )
    return points


def test_extraction_retrouve_vitesse_et_pente_connues():
    activite = _fabrique_activite(vitesse_m_s=2.5, pente=0.08)
    pairs = extract_slope_speed_pairs(activite)

    assert len(pairs) > 5
    for slope, speed in pairs:
        assert speed == pytest.approx(2.5, rel=0.05)
        assert slope == pytest.approx(0.08, rel=0.1)


def test_liste_vide_ne_produit_aucune_paire():
    assert extract_slope_speed_pairs([]) == []


def test_pas_trop_courts_sont_ignores():
    # Points espacés de 1 s : sous MIN_SEGMENT_DURATION_S, tout est filtré.
    activite = _fabrique_activite(vitesse_m_s=2.5, pente=0.08, n_points=10)
    for p in activite:
        p.time = activite[0].time  # écrase l'écart de temps entre tous les points
    assert extract_slope_speed_pairs(activite) == []
