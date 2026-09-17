import pytest

from app.core.gap import gap_factor
from app.core.gap_calibration import MIN_SAMPLES_PER_BIN, aggregate_by_slope, build_gap_model


def _pairs_suivant_minetti(slope: float, flat_speed: float = 3.0, n: int = 30) -> list[tuple[float, float]]:
    """Génère des couples (pente, vitesse) qui respectent exactement la courbe théorique."""
    speed = flat_speed / gap_factor(slope)
    return [(slope, speed)] * n


def test_aggregate_ignore_les_bins_trop_pauvres():
    pairs = [(0.08, 2.0)] * (MIN_SAMPLES_PER_BIN - 1)
    assert aggregate_by_slope(pairs) == []


def test_aggregate_garde_les_bins_suffisamment_peuples():
    pairs = [(0.08, 2.0)] * MIN_SAMPLES_PER_BIN
    bins = aggregate_by_slope(pairs)
    assert len(bins) == 1
    assert bins[0].n_samples == MIN_SAMPLES_PER_BIN
    assert bins[0].median_speed_m_s == pytest.approx(2.0)


def test_calibrage_sur_donnees_conformes_a_minetti_donne_un_rmse_quasi_nul():
    activite = (
        _pairs_suivant_minetti(0.0)
        + _pairs_suivant_minetti(0.08)
        + _pairs_suivant_minetti(-0.08)
        + _pairs_suivant_minetti(0.16)
    )
    modele = build_gap_model([activite], source="test")

    assert modele.rmse == pytest.approx(0.0, abs=1e-6)
    assert modele.n_activities == 1


def test_absence_de_terrain_plat_leve_une_erreur():
    activite = _pairs_suivant_minetti(0.12)
    with pytest.raises(ValueError):
        build_gap_model([activite], source="test")
