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

from pathlib import Path

from app.core.gap_calibration import calibrate_gap_curve


GPX_TEMPLATE = """<?xml version="1.0"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
  <trk><trkseg>
    {points}
  </trkseg></trk>
</gpx>"""

POINT_TEMPLATE = (
    '<trkpt lat="{lat}" lon="11.3"><ele>{ele}</ele>'
    '<time>2026-06-01T08:00:{sec:02d}Z</time></trkpt>'
)


def _write_flat_gpx(path: Path, n: int = 40) -> None:
    points = "\n".join(
        POINT_TEMPLATE.format(lat=43.5 + i * 0.0002, ele=100.0, sec=i * 1)
        for i in range(n)
    )
    path.write_text(GPX_TEMPLATE.format(points=points), encoding="utf-8")


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


def test_doublon_exact_n_est_compte_qu_une_fois(tmp_path):
    _write_flat_gpx(tmp_path / "sortie1.gpx")
    (tmp_path / "sortie1_copie.gpx").write_bytes((tmp_path / "sortie1.gpx").read_bytes())

    modele = calibrate_gap_curve(str(tmp_path))
    assert modele.n_activities == 1
