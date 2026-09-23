from pydantic import BaseModel

from app.core.athlete import AthleteProfile
from app.core.gap_calibration import GapModel, effective_gap_factor
from app.core.models import Segment
from app.core.weather import WeatherForecast

BASE_DRIFT_PER_HOUR = 0.015
REFERENCE_RIEGEL_EXPONENT = 1.06
HEAT_THRESHOLD_C = 15.0
HEAT_PENALTY_PER_DEGREE = 0.01
WALK_SLOPE_THRESHOLD = 0.20
WALK_PACE_S_PER_KM = 750.0
PACE_UNCERTAINTY = 0.07
CONVERGENCE_TOLERANCE = 0.03
MAX_CALIBRATION_STEPS = 25


class SegmentPace(BaseModel):
    """Consigne d'allure pour un tronçon du parcours."""

    index: int
    kind: str
    distance_m: float
    avg_slope: float
    pace_s_per_km: float
    vertical_speed_m_per_h: float
    time_s: float
    cumulative_time_s: float
    time_low_s: float
    time_high_s: float


class PacingPlan(BaseModel):
    """Plan d'allure complet, segment par segment."""

    segments: list[SegmentPace]
    total_time_s: float
    target_time_s: float | None
    converged: bool
    weather_penalty: float
    notes: list[str]


def weather_penalty(temp_c: float, humidity_pct: float) -> float:
    """Ralentissement dû à la chaleur, amplifié par l'humidité.

    En dessous de 15 °C l'effet est négligeable ; au-delà, on compte environ 1 %
    de perte par degré, majorée quand l'air est humide (la sudation évacue moins bien).
    """
    if temp_c <= HEAT_THRESHOLD_C:
        return 1.0

    excess_c = temp_c - HEAT_THRESHOLD_C
    humidity_amplifier = 1.0 + max(0.0, humidity_pct - 50.0) / 100.0
    return 1.0 + HEAT_PENALTY_PER_DEGREE * excess_c * humidity_amplifier


def fatigue_drift(elapsed_h: float, riegel_exponent: float) -> float:
    """Majoration du temps due à la fatigue accumulée depuis le départ.

    L'exposant d'endurance module la pente de cette dérive : un athlète qui perd
    beaucoup de vitesse avec la distance (k élevé) se dégrade plus vite ici aussi.
    """
    rate = BASE_DRIFT_PER_HOUR * (riegel_exponent / REFERENCE_RIEGEL_EXPONENT)
    return 1.0 + rate * elapsed_h


def _simulate(
    segments: list[Segment],
    athlete: AthleteProfile,
    gap_model: GapModel,
    penalty: float,
    effort: float,
) -> list[SegmentPace]:
    """Déroule le parcours segment par segment pour un niveau d'effort donné."""
    paces: list[SegmentPace] = []
    cumulative_s = 0.0

    for segment in segments:
        gap = effective_gap_factor(gap_model, segment.avg_slope)
        pace = athlete.flat_pace_s_per_km * gap * penalty * effort
        pace *= fatigue_drift(cumulative_s / 3600.0, athlete.riegel_exponent)

        if segment.avg_slope >= WALK_SLOPE_THRESHOLD:
            pace = max(pace, WALK_PACE_S_PER_KM)

        time_s = pace * segment.distance_m / 1000.0
        cumulative_s += time_s
        vertical = segment.elev_gain_m / time_s * 3600.0 if time_s > 0 else 0.0

        paces.append(
            SegmentPace(
                index=segment.index,
                kind=segment.kind,
                distance_m=segment.distance_m,
                avg_slope=segment.avg_slope,
                pace_s_per_km=pace,
                vertical_speed_m_per_h=vertical,
                time_s=time_s,
                cumulative_time_s=cumulative_s,
                time_low_s=time_s * (1.0 - PACE_UNCERTAINTY),
                time_high_s=time_s * (1.0 + PACE_UNCERTAINTY),
            )
        )

    return paces


def compute_pacing_plan(
    segments: list[Segment],
    athlete: AthleteProfile,
    gap_model: GapModel,
    weather: WeatherForecast,
    target_time_s: float | None = None,
) -> PacingPlan:
    """Outil de l'agent : produit l'allure cible par segment pour atteindre l'objectif."""
    if not segments:
        raise ValueError("Aucun segment : impossible de construire un plan d'allure.")

    penalty = weather_penalty(weather.stats.temp_mean_c, weather.stats.humidity_mean_pct)
    effort = 1.0
    paces = _simulate(segments, athlete, gap_model, penalty, effort)

    if target_time_s:
        # Le temps dépend de l'effort de façon quasi linéaire : quelques itérations
        # suffisent à converger, malgré la dérive de fatigue qui rend le lien non exact.
        for _ in range(MAX_CALIBRATION_STEPS):
            total_s = paces[-1].cumulative_time_s
            if abs(total_s - target_time_s) / target_time_s < 0.001:
                break
            effort *= target_time_s / total_s
            paces = _simulate(segments, athlete, gap_model, penalty, effort)

    total_s = paces[-1].cumulative_time_s
    converged = (
        target_time_s is None
        or abs(total_s - target_time_s) / target_time_s <= CONVERGENCE_TOLERANCE
    )

    notes: list[str] = []
    if penalty > 1.0:
        notes.append(
            f"Pénalité météo de {(penalty - 1) * 100:.1f} % appliquée "
            f"({weather.stats.temp_mean_c:.1f} °C, {weather.stats.humidity_mean_pct:.0f} % d'humidité)."
        )
    if gap_model.n_activities > 0:
        notes.append(f"Correction de pente calibrée sur {gap_model.n_activities} activité(s).")
    else:
        notes.append("Correction de pente théorique (Minetti), aucun calibrage personnel.")
    if target_time_s and not converged:
        notes.append(
            f"Objectif de {target_time_s / 3600:.2f} h non atteignable : le plan converge "
            f"vers {total_s / 3600:.2f} h (plafond d'allure de marche en forte pente)."
        )

    return PacingPlan(
        segments=paces,
        total_time_s=total_s,
        target_time_s=target_time_s,
        converged=converged,
        weather_penalty=penalty,
        notes=notes,
    )
