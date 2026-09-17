import pytest

from app.core.gap import adjusted_pace_s_per_km, gap_factor


def test_plat_vaut_un():
    assert gap_factor(0.0) == pytest.approx(1.0)


def test_montee_plus_couteuse_que_plat():
    assert gap_factor(0.10) > 1.0
    assert gap_factor(0.20) > gap_factor(0.10)


def test_descente_douce_moins_couteuse_que_plat():
    assert gap_factor(-0.10) < 1.0


def test_pente_extreme_est_bornee():
    assert gap_factor(0.80) == gap_factor(0.45)


def test_plafond_de_marche_en_forte_pente():
    pace = adjusted_pace_s_per_km(flat_pace_s_per_km=300, slope=0.25)
    assert pace >= 750