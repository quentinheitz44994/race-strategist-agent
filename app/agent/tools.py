from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from app.core.activity import load_activity_gpx  # noqa: F401  (réexporté pour usage direct si besoin)
from app.core.athlete import AthleteProfile, load_athlete_profile
from app.core.gap_calibration import GapModel, calibrate_gap_curve
from app.core.gpx import load_route
from app.core.models import RouteProfile, Segment
from app.core.segmentation import segment_route
from app.core.weather import WeatherForecast, get_weather_forecast


@dataclass
class ToolSpec:
    """Un outil exposé à l'agent : la fonction réelle, nommée et documentée pour le LLM."""

    name: str
    func: Callable[..., Any]
    description: str


def _weather_tool(lat: float, lon: float, race_date: date) -> WeatherForecast:
    """Wrapper sans le paramètre `today`, réservé aux tests."""
    return get_weather_forecast(lat, lon, race_date)


TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="load_route",
        func=load_route,
        description=(
            "Lit un fichier GPX et renvoie le profil du parcours : distance totale, "
            "D+/D-, série de points lissée."
        ),
    ),
    ToolSpec(
        name="segment_route",
        func=segment_route,
        description=(
            "Découpe un RouteProfile en segments homogènes (montée/descente/plat), "
            "chacun avec sa distance, son D+/D- et sa pente moyenne."
        ),
    ),
    ToolSpec(
        name="load_athlete_profile",
        func=load_athlete_profile,
        description=(
            "Lit le profil athlète déclaré (records, charge d'entraînement) et calcule "
            "l'allure de référence, l'exposant d'endurance et les avertissements associés."
        ),
    ),
    ToolSpec(
        name="calibrate_gap_curve",
        func=calibrate_gap_curve,
        description=(
            "Calibre la correction d'allure en pente à partir des activités locales de "
            "l'athlète ; utilise la courbe théorique de Minetti si aucune activité n'est disponible."
        ),
    ),
    ToolSpec(
        name="get_weather_forecast",
        func=_weather_tool,
        description=(
            "Donne la météo attendue à une position et une date : prévision si la course "
            "est à moins de 14 jours, moyenne climatologique sur 5 ans sinon."
        ),
    ),
]


def get_tool(name: str) -> ToolSpec:
    for tool in TOOLS:
        if tool.name == name:
            return tool
    raise KeyError(f"Outil inconnu : {name}")
