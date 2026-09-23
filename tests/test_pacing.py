import pytest

from app.core.athlete import AthleteProfile
from app.core.gap_calibration import GapModel
from app.core.models import Segment
from app.core.pacing import (
    CONVERGENCE_TOLERANCE,
    compute_pacing_plan,
    fatigue_drift,
    weather_penalty,
)
from app.core.weather import DayStats, WeatherForecast


def _athlete(flat_pace_s_per_km: float = 300.0, exponent: float = 1.06) -> AthleteProfile:
    return AthleteProfile(
        name="test",
        weight_kg=70,
        reference_distance_m=42_195,
        flat_pace_s_per_km=flat_pace_s_per_km,
        predicted_time_s=flat_pace_s_per_km * 42.195,
        riegel_exponent=exponent,
        riegel_coefficient=0.12,
        endurance_rating="dans la norme",
        warnings=[],
        source="test",
    )


def _gap_model_theorique() -> GapModel:
    return GapModel(
        n_activities=0,
        n_samples=0,
        flat_speed_m_s=0.0,
        empirical_factor={},
        theoretical_factor={},
        rmse=0.0,
        source="théorique (Minetti)",
    )


def _weather(temp_c: float = 10.0, humidity_pct: float = 50.0) -> WeatherForecast:
    return WeatherForecast(
        race_date="2027-03-20",
        lat=43.5,
        lon=11.3,
        stats=DayStats(
            temp_min_c=temp_c - 5,
            temp_max_c=temp_c + 5,
            temp_mean_c=temp_c,
            humidity_mean_pct=humidity_pct,
            precipitation_mm=0.0,
            wind_max_kmh=10.0,
        ),
        source="climatologie",
        detail="test",
    )


def _segments_plats(n: int = 10, distance_m: float = 5_000.0) -> list[Segment]:
    return [
        Segment(
            index=i,
            start_m=i * distance_m,
            end_m=(i + 1) * distance_m,
            distance_m=distance_m,
            elev_gain_m=0.0,
            elev_loss_m=0.0,
            avg_slope=0.0,
            alt_min_m=100.0,
            alt_max_m=100.0,
            kind="plat",
        )
        for i in range(n)
    ]


def test_pas_de_penalite_meteo_en_dessous_de_quinze_degres():
    assert weather_penalty(10.0, 60.0) == 1.0
    assert weather_penalty(15.0, 90.0) == 1.0


def test_la_chaleur_ralentit_et_l_humidite_amplifie():
    sec = weather_penalty(25.0, 40.0)
    humide = weather_penalty(25.0, 90.0)
    assert sec > 1.0
    assert humide > sec


def test_la_derive_de_fatigue_croit_avec_le_temps_et_avec_l_exposant():
    assert fatigue_drift(0.0, 1.06) == 1.0
    assert fatigue_drift(5.0, 1.06) > fatigue_drift(1.0, 1.06)
    assert fatigue_drift(5.0, 1.20) > fatigue_drift(5.0, 1.06)


def test_sans_objectif_le_plan_reflete_l_allure_de_reference():
    plan = compute_pacing_plan(
        _segments_plats(), _athlete(300.0), _gap_model_theorique(), _weather()
    )
    # 50 km à 300 s/km = 15 000 s, plus la seule dérive de fatigue.
    assert 15_000 < plan.total_time_s < 16_500
    assert plan.weather_penalty == 1.0
    assert len(plan.segments) == 10


def test_le_temps_total_converge_vers_l_objectif():
    target = 14_400.0  # 4 h
    plan = compute_pacing_plan(
        _segments_plats(), _athlete(300.0), _gap_model_theorique(), _weather(),
        target_time_s=target,
    )

    assert plan.converged
    assert abs(plan.total_time_s - target) / target <= CONVERGENCE_TOLERANCE


def test_le_temps_cumule_est_croissant_et_coherent_avec_le_total():
    plan = compute_pacing_plan(
        _segments_plats(), _athlete(), _gap_model_theorique(), _weather()
    )

    cumuls = [s.cumulative_time_s for s in plan.segments]
    assert cumuls == sorted(cumuls)
    assert plan.total_time_s == pytest.approx(sum(s.time_s for s in plan.segments))
    assert plan.total_time_s == pytest.approx(cumuls[-1])


def test_la_montee_est_plus_lente_que_le_plat():
    plat, montee = _segments_plats(2)
    montee.avg_slope = 0.10
    montee.kind = "montée"
    montee.elev_gain_m = 500.0

    plan = compute_pacing_plan(
        [plat, montee], _athlete(), _gap_model_theorique(), _weather()
    )

    assert plan.segments[1].pace_s_per_km > plan.segments[0].pace_s_per_km
    assert plan.segments[1].vertical_speed_m_per_h > 0


def test_le_calibrage_empirique_prime_sur_la_theorie():
    empirique = GapModel(
        n_activities=3,
        n_samples=500,
        flat_speed_m_s=3.0,
        empirical_factor={"0.00": 1.0, "0.08": 3.0},  # volontairement très pénalisant
        theoretical_factor={"0.00": 1.0, "0.08": 1.5},
        rmse=0.4,
        source="3 activités locales",
    )
    _, montee = _segments_plats(2)
    montee.avg_slope = 0.08

    plan_empirique = compute_pacing_plan(
        [montee], _athlete(300.0), empirique, _weather()
    )
    plan_theorique = compute_pacing_plan(
        [montee], _athlete(300.0), _gap_model_theorique(), _weather()
    )

    assert plan_empirique.segments[0].pace_s_per_km > plan_theorique.segments[0].pace_s_per_km


def test_plan_sans_segment_leve_une_erreur():
    with pytest.raises(ValueError):
        compute_pacing_plan([], _athlete(), _gap_model_theorique(), _weather())
