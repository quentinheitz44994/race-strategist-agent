import pytest
from pydantic import ValidationError

from app.core.athlete import (
    DEFAULT_RIEGEL_EXPONENT,
    RIEGEL_MAX,
    AthleteInput,
    Record,
    build_profile,
    fit_riegel,
    load_athlete_profile,
)


def _records_from_exponent(exponent: float, coefficient: float = 0.12) -> list[Record]:
    """Fabrique des records qui suivent exactement T = a·D^k."""
    return [
        Record(label=f"{d / 1000:.0f} km", distance_m=d, time_s=coefficient * d**exponent)
        for d in (5_000, 10_000, 21_097, 42_195)
    ]


def test_fit_riegel_retrouve_un_exposant_connu():
    coefficient, exponent, fitted = fit_riegel(_records_from_exponent(1.08))
    assert fitted
    assert exponent == pytest.approx(1.08, abs=1e-6)
    assert coefficient == pytest.approx(0.12, rel=1e-6)


def test_un_seul_record_retombe_sur_l_exposant_par_defaut():
    records = [Record(label="10 km", distance_m=10_000, time_s=2_520)]
    coefficient, exponent, fitted = fit_riegel(records)
    assert not fitted
    assert exponent == DEFAULT_RIEGEL_EXPONENT
    assert coefficient * 10_000**exponent == pytest.approx(2_520)


def test_exposant_aberrant_est_borne_et_recale_sur_le_record_le_plus_long():
    records = [
        Record(label="5 km", distance_m=5_000, time_s=1_080),
        Record(label="marathon", distance_m=42_195, time_s=21_600),
    ]
    coefficient, exponent, _ = fit_riegel(records)
    assert exponent == RIEGEL_MAX
    assert coefficient * 42_195**exponent == pytest.approx(21_600)


def test_records_incoherents_declenchent_un_avertissement():
    athlete = AthleteInput(
        name="test",
        weight_kg=70,
        height_cm=178,
        records=[
            Record(label="10 km", distance_m=10_000, time_s=3_000),
            Record(label="semi", distance_m=21_097, time_s=5_400),
        ],
        training={
            "weekly_distance_km": 50,
            "weekly_elev_gain_m": 800,
            "longest_run_km": 25,
            "longest_run_duration_s": 9_000,
            "max_elev_gain_single_run_m": 900,
            "experience": "intermédiaire",
        },
    )
    profile = build_profile(athlete, reference_distance_m=42_195)
    assert any("incohérents" in w for w in profile.warnings)


def test_vitesse_impossible_rejetee_a_la_saisie():
    with pytest.raises(ValidationError):
        Record(label="marathon", distance_m=42_195, time_s=1_800)


def test_le_profil_d_exemple_est_exploitable_et_sans_avertissement():
    profile = load_athlete_profile(73_000, path="config/athlete.example.json")
    assert profile.warnings == []
    assert 1.00 <= profile.riegel_exponent <= 1.30
    assert profile.source.endswith("athlete.example.json")
