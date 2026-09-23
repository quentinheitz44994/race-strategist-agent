from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.core.gap import gap_factor
from app.core.gap_calibration import (
    MIN_SAMPLES_PER_BIN,
    aggregate_by_slope,
    build_gap_model,
    calibrate_gap_curve,
)

GPX_TEMPLATE = """<?xml version="1.0"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
  <trk><trkseg>
{points}
  </trkseg></trk>
</gpx>"""

POINT_TEMPLATE = (
    '<trkpt lat="{lat:.6f}" lon="11.300000"><ele>{ele:.1f}</ele>'
    "<time>{time}</time></trkpt>"
)

METRES_PAR_DEGRE_LAT = 111_320.0


def _pairs_suivant_minetti(
    slope: float, flat_speed: float = 3.0, n: int = 30
) -> list[tuple[float, float]]:
    """Génère des couples (pente, vitesse) qui respectent exactement la courbe théorique."""
    speed = flat_speed / gap_factor(slope)
    return [(slope, speed)] * n


def _write_flat_gpx(path: Path, n_points: int = 100, speed_m_s: float = 3.0) -> None:
    """Écrit un .gpx d'activité plate et plausible : vitesse et altitude constantes.

    Points espacés de 2 s, soit 6 m à 3 m/s : il faut donc 4 points pour franchir
    à la fois MIN_SEGMENT_DISTANCE_M (20 m) et MIN_SEGMENT_DURATION_S (5 s).
    """
    start_time = datetime(2026, 6, 1, 8, 0, 0)
    step_s = 2.0

    points = []
    for i in range(n_points):
        elapsed_s = i * step_s
        distance_m = speed_m_s * elapsed_s
        points.append(
            POINT_TEMPLATE.format(
                lat=43.5 + distance_m / METRES_PAR_DEGRE_LAT,
                ele=100.0,
                time=(start_time + timedelta(seconds=elapsed_s)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
        )

    path.write_text(GPX_TEMPLATE.format(points="\n".join(points)), encoding="utf-8")


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


def test_dossier_absent_replie_sur_minetti(tmp_path):
    modele = calibrate_gap_curve(str(tmp_path / "n_existe_pas"))
    assert modele.n_activities == 0
    assert "théorique" in modele.source


def test_dossier_vide_replie_sur_minetti(tmp_path):
    modele = calibrate_gap_curve(str(tmp_path))
    assert modele.n_activities == 0
    assert "théorique" in modele.source


def test_fichier_illisible_est_ignore_sans_planter(tmp_path):
    (tmp_path / "corrompu.gpx").write_text("ceci n'est pas du xml", encoding="utf-8")
    modele = calibrate_gap_curve(str(tmp_path))
    assert "théorique" in modele.source  # aucune activité valide, donc repli


def test_activite_plate_est_calibree(tmp_path):
    _write_flat_gpx(tmp_path / "sortie1.gpx")

    modele = calibrate_gap_curve(str(tmp_path))

    assert modele.n_activities == 1
    assert modele.n_samples >= MIN_SAMPLES_PER_BIN
    assert modele.flat_speed_m_s == pytest.approx(3.0, rel=0.05)


def test_doublon_exact_n_est_compte_qu_une_fois(tmp_path):
    _write_flat_gpx(tmp_path / "sortie1.gpx")
    (tmp_path / "sortie1_copie.gpx").write_bytes((tmp_path / "sortie1.gpx").read_bytes())

    modele = calibrate_gap_curve(str(tmp_path))

    assert modele.n_activities == 1
    assert modele.n_samples >= MIN_SAMPLES_PER_BIN
