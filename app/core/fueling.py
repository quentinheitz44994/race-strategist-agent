from typing import Literal

from pydantic import BaseModel

HEAT_THRESHOLD_C = 15.0
FLUID_PER_DEGREE_ML = 20.0
MAX_FLUID_ML_PER_H = 1000.0
SODIUM_PER_LITRE_MG = 700.0

Intensity = Literal["faible", "modéré", "élevé"]

INTENSITY_FACTOR: dict[str, float] = {
    "faible": 0.8,
    "modéré": 1.0,
    "élevé": 1.15,
}

DISCLAIMER = (
    "Valeurs indicatives, à tester à l'entraînement et jamais à découvrir le jour de la course. "
    "Elles ne constituent pas un avis médical ou diététique."
)


class Range(BaseModel):
    """Fourchette basse/haute d'une recommandation."""

    low: float
    high: float


class FuelingPlan(BaseModel):
    """Plan nutrition et hydratation pour la durée et les conditions estimées."""

    duration_h: float
    temp_c: float
    intensity: str
    carbs_g_per_h: Range
    fluid_ml_per_h: Range
    sodium_mg_per_h: Range
    total_carbs_g: Range
    total_fluid_ml: Range
    notes: list[str]
    disclaimer: str


def _carb_range(duration_h: float, factor: float) -> Range:
    """Glucides horaires : le besoin monte avec la durée, jusqu'à la limite d'absorption."""
    if duration_h < 1.0:
        low, high = 0.0, 30.0
    elif duration_h < 2.5:
        low, high = 30.0, 60.0
    else:
        low, high = 60.0, 90.0

    return Range(low=low * factor, high=high * factor)


def _fluid_range(temp_c: float, factor: float) -> Range:
    """Hydratation horaire : base tempérée, majorée par degré au-dessus de 15 °C."""
    low, high = 400.0, 700.0
    if temp_c > HEAT_THRESHOLD_C:
        extra = (temp_c - HEAT_THRESHOLD_C) * FLUID_PER_DEGREE_ML
        low += extra
        high += extra

    return Range(
        low=min(low * factor, MAX_FLUID_ML_PER_H),
        high=min(high * factor, MAX_FLUID_ML_PER_H),
    )


def compute_fueling_plan(
    duration_h: float,
    temp_c: float,
    intensity: Intensity = "modéré",
) -> FuelingPlan:
    """Outil de l'agent : recommandations horaires de glucides, liquide et sodium."""
    if duration_h <= 0:
        raise ValueError("La durée estimée doit être strictement positive.")

    factor = INTENSITY_FACTOR.get(intensity, 1.0)
    carbs = _carb_range(duration_h, factor)
    fluid = _fluid_range(temp_c, factor)

    # Le sodium suit le volume bu : c'est la sueur perdue qu'il s'agit de compenser.
    sodium = Range(
        low=fluid.low / 1000.0 * SODIUM_PER_LITRE_MG,
        high=fluid.high / 1000.0 * SODIUM_PER_LITRE_MG,
    )

    notes: list[str] = []
    if temp_c > HEAT_THRESHOLD_C:
        notes.append(
            f"Hydratation majorée : {temp_c:.1f} °C attendus, soit "
            f"{(temp_c - HEAT_THRESHOLD_C) * FLUID_PER_DEGREE_ML:.0f} ml/h de plus qu'en conditions tempérées."
        )
    if duration_h >= 2.5:
        notes.append(
            "Au-delà de 2 h 30, viser le haut de la fourchette glucidique et fractionner "
            "les apports toutes les 20 à 30 minutes."
        )
    if fluid.high >= MAX_FLUID_ML_PER_H:
        notes.append("Apport liquide plafonné à 1 L/h : au-delà, le risque digestif l'emporte.")

    return FuelingPlan(
        duration_h=duration_h,
        temp_c=temp_c,
        intensity=intensity,
        carbs_g_per_h=carbs,
        fluid_ml_per_h=fluid,
        sodium_mg_per_h=sodium,
        total_carbs_g=Range(low=carbs.low * duration_h, high=carbs.high * duration_h),
        total_fluid_ml=Range(low=fluid.low * duration_h, high=fluid.high * duration_h),
        notes=notes,
        disclaimer=DISCLAIMER,
    )
