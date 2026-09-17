import json
import math
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field, model_validator

DEFAULT_RIEGEL_EXPONENT = 1.06
RIEGEL_MIN, RIEGEL_MAX = 1.00, 1.30
EXTRAPOLATION_LIMIT = 2.5


class Record(BaseModel):
    """Une performance chronométrée déclarée par l'athlète."""

    label: str
    distance_m: float = Field(gt=0, le=500_000)
    time_s: float = Field(gt=0)

    @property
    def speed_m_s(self) -> float:
        return self.distance_m / self.time_s

    @model_validator(mode="after")
    def _check_plausible_speed(self) -> "Record":
        if not 1.0 <= self.speed_m_s <= 12.0:
            raise ValueError(
                f"Record '{self.label}' : vitesse de {self.speed_m_s:.2f} m/s hors des bornes "
                "physiologiques [1.0 ; 12.0]. Vérifie la distance et le temps."
            )
        return self


class TrainingLoad(BaseModel):
    """Charge d'entraînement déclarée sur les dernières semaines représentatives."""

    weekly_distance_km: float = Field(ge=0, le=300)
    weekly_elev_gain_m: float = Field(ge=0, le=15_000)
    longest_run_km: float = Field(gt=0, le=300)
    longest_run_duration_s: float = Field(gt=0, le=200_000)
    max_elev_gain_single_run_m: float = Field(ge=0, le=12_000)
    experience: Literal["débutant", "intermédiaire", "confirmé", "expert"]


class AthleteInput(BaseModel):
    """Ce que l'utilisateur déclare. Aucune valeur calculée ici."""

    name: str
    weight_kg: float = Field(gt=30, lt=200)
    height_cm: float = Field(gt=120, lt=230)
    vo2max: float | None = Field(default=None, gt=20, lt=95)
    vma_kmh: float | None = Field(default=None, gt=8, lt=25)
    records: list[Record] = Field(min_length=1)
    training: TrainingLoad

class AthleteProfile(BaseModel):
    """Ce que le système déduit. Aucune valeur saisie directement ici."""

    name: str
    weight_kg: float
    reference_distance_m: float
    flat_pace_s_per_km: float
    predicted_time_s: float
    riegel_exponent: float
    riegel_coefficient: float
    endurance_rating: str
    warnings: list[str]
    source: str

def _anchor_coefficient(records: list[Record], exponent: float) -> float:
    """Cale la courbe sur le record le plus long, celui qui compte pour extrapoler."""
    longest = max(records, key=lambda r: r.distance_m)
    return longest.time_s / longest.distance_m**exponent


def fit_riegel(records: list[Record]) -> tuple[float, float, bool]:
    """Ajuste T = a·D^k sur les records.

    Renvoie (coefficient, exposant, ajustement_reel).
    """
    distances = np.array([r.distance_m for r in records], dtype=float)
    times = np.array([r.time_s for r in records], dtype=float)

    if len(np.unique(distances)) < 2:
        return _anchor_coefficient(records, DEFAULT_RIEGEL_EXPONENT), DEFAULT_RIEGEL_EXPONENT, False

    raw_exponent, log_coefficient = np.polyfit(np.log(distances), np.log(times), 1)
    exponent = float(min(max(raw_exponent, RIEGEL_MIN), RIEGEL_MAX))

    if exponent != raw_exponent:
        return _anchor_coefficient(records, exponent), exponent, True
    return float(math.exp(log_coefficient)), exponent, True


def predict_time_s(coefficient: float, exponent: float, distance_m: float) -> float:
    return coefficient * distance_m**exponent

def rate_endurance(exponent: float) -> str:
    """Traduit l'exposant en qualification lisible. Plus k est bas, mieux c'est."""
    if exponent < 1.04:
        return "excellente"
    if exponent < 1.09:
        return "dans la norme"
    if exponent < 1.15:
        return "perfectible"
    return "point faible marqué"


def _sustainable_vma_fraction(distance_m: float) -> float:
    """Fraction de VMA tenable, décroissante avec la distance."""
    if distance_m <= 10_000:
        return 0.92
    if distance_m <= 21_097:
        return 0.88
    if distance_m <= 42_195:
        return 0.84
    return 0.78


def collect_warnings(
    athlete: AthleteInput,
    reference_distance_m: float,
    fitted: bool,
    predicted_time_s: float,
) -> list[str]:
    warnings: list[str] = []

    if not fitted:
        warnings.append(
            f"Un seul record exploitable : exposant par défaut ({DEFAULT_RIEGEL_EXPONENT}) "
            "appliqué au lieu d'un ajustement personnel."
        )
    elif len(athlete.records) < 3:
        warnings.append(
            f"Exposant ajusté sur {len(athlete.records)} records seulement : estimation peu robuste."
        )

    ordered = sorted(athlete.records, key=lambda r: r.distance_m)
    for shorter, longer in zip(ordered, ordered[1:]):
        if longer.speed_m_s > shorter.speed_m_s * 1.02:
            warnings.append(
                f"Records incohérents : '{longer.label}' est plus rapide au kilomètre que "
                f"'{shorter.label}' alors qu'il est plus long."
            )

    longest_m = max(r.distance_m for r in athlete.records)
    ratio = reference_distance_m / longest_m
    if ratio > EXTRAPOLATION_LIMIT:
        warnings.append(
            f"Extrapolation à {ratio:.1f}× la plus longue performance connue "
            f"({longest_m / 1000:.1f} km) : prédiction indicative, pas fiable."
        )

    if athlete.vma_kmh is not None:
        fraction = (reference_distance_m / predicted_time_s) * 3.6 / athlete.vma_kmh
        limit = _sustainable_vma_fraction(reference_distance_m)
        if fraction > limit:
            warnings.append(
                f"Allure prédite à {fraction:.0%} de la VMA déclarée, au-delà des {limit:.0%} "
                "tenables sur cette distance : objectif probablement hors de portée."
            )

    return warnings

def build_profile(
    athlete: AthleteInput,
    reference_distance_m: float,
    source: str = "saisie utilisateur",
) -> AthleteProfile:
    """Dérive le profil exploitable à partir de la saisie, pour une distance de course donnée."""
    coefficient, exponent, fitted = fit_riegel(athlete.records)
    predicted_time_s = predict_time_s(coefficient, exponent, reference_distance_m)

    return AthleteProfile(
        name=athlete.name,
        weight_kg=athlete.weight_kg,
        reference_distance_m=reference_distance_m,
        flat_pace_s_per_km=predicted_time_s / (reference_distance_m / 1000),
        predicted_time_s=predicted_time_s,
        riegel_exponent=exponent,
        riegel_coefficient=coefficient,
        endurance_rating=rate_endurance(exponent),
        warnings=collect_warnings(athlete, reference_distance_m, fitted, predicted_time_s),
        source=source,
    )


def load_athlete_profile(
    reference_distance_m: float,
    path: str = "config/athlete.json",
) -> AthleteProfile:
    """Outil de l'agent : lit le fichier de saisie et renvoie le profil dérivé."""
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    athlete = AthleteInput.model_validate(payload)
    return build_profile(athlete, reference_distance_m, source=path)
