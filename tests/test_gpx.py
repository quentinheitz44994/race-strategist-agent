import numpy as np

from app.core.gpx import compute_elevation_change, haversine_m, smooth_elevation


def test_distance_connue():
    # Un degré de latitude vaut environ 111 km.
    d = haversine_m(48.0, 2.0, 49.0, 2.0)
    assert 110_000 < d < 112_000


def test_seuil_ignore_le_bruit():
    bruit = np.array([100.0, 100.3, 99.8, 100.2, 100.0])
    gain, loss = compute_elevation_change(bruit, threshold_m=1.0)
    assert gain == 0.0
    assert loss == 0.0


def test_montee_franche_est_comptee():
    montee = np.array([100.0, 110.0, 120.0])
    gain, loss = compute_elevation_change(montee, threshold_m=1.0)
    assert gain == 20.0
    assert loss == 0.0


def test_lissage_reduit_le_denivele():
    rng = np.random.default_rng(42)
    vraie_pente = np.linspace(100, 200, 500)
    bruitee = vraie_pente + rng.normal(0, 1.5, 500)

    gain_brut, _ = compute_elevation_change(bruitee, threshold_m=0.0)
    gain_lisse, _ = compute_elevation_change(smooth_elevation(bruitee), threshold_m=0.0)

    assert gain_lisse < gain_brut