from datetime import date
from typing import Literal

import httpx
from pydantic import BaseModel

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_HORIZON_DAYS = 14
CLIMATOLOGY_YEARS = 5
HOURLY_VARIABLES = "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m"
REQUEST_TIMEOUT_S = 10.0


class WeatherUnavailable(RuntimeError):
    """Open-Meteo n'a pas répondu, ou n'a renvoyé aucune donnée exploitable."""


class DayStats(BaseModel):
    """Indicateurs d'une journée, agrégés depuis une série horaire."""

    temp_min_c: float
    temp_max_c: float
    temp_mean_c: float
    humidity_mean_pct: float
    precipitation_mm: float
    wind_max_kmh: float


class WeatherForecast(BaseModel):
    """Météo attendue le jour de la course, avec l'origine de la donnée."""

    race_date: date
    lat: float
    lon: float
    stats: DayStats
    source: Literal["prévision", "climatologie"]
    detail: str


def _clean(values: list) -> list[float]:
    """Open-Meteo renvoie None pour les heures sans mesure."""
    return [float(v) for v in values if v is not None]


def summarize_hourly(hourly: dict) -> DayStats:
    """Réduit une série horaire Open-Meteo en indicateurs journaliers."""
    temps = _clean(hourly.get("temperature_2m", []))
    humidity = _clean(hourly.get("relative_humidity_2m", []))
    precipitation = _clean(hourly.get("precipitation", []))
    wind = _clean(hourly.get("wind_speed_10m", []))

    if not temps:
        raise WeatherUnavailable("Série horaire sans température exploitable.")

    return DayStats(
        temp_min_c=min(temps),
        temp_max_c=max(temps),
        temp_mean_c=sum(temps) / len(temps),
        humidity_mean_pct=sum(humidity) / len(humidity) if humidity else 0.0,
        precipitation_mm=sum(precipitation),
        wind_max_kmh=max(wind) if wind else 0.0,
    )


def average_stats(samples: list[DayStats]) -> DayStats:
    """Moyenne des années échantillonnées : c'est ce qui constitue la climatologie."""
    n = len(samples)
    if n == 0:
        raise WeatherUnavailable("Aucune année exploitable pour la climatologie.")

    return DayStats(
        temp_min_c=sum(s.temp_min_c for s in samples) / n,
        temp_max_c=sum(s.temp_max_c for s in samples) / n,
        temp_mean_c=sum(s.temp_mean_c for s in samples) / n,
        humidity_mean_pct=sum(s.humidity_mean_pct for s in samples) / n,
        precipitation_mm=sum(s.precipitation_mm for s in samples) / n,
        wind_max_kmh=sum(s.wind_max_kmh for s in samples) / n,
    )

def _fetch_day(url: str, lat: float, lon: float, day: date) -> dict:
    """Un appel HTTP, une journée. Isolé pour être remplaçable en test."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": day.isoformat(),
        "end_date": day.isoformat(),
        "hourly": HOURLY_VARIABLES,
        "timezone": "auto",
    }
    try:
        response = httpx.get(url, params=params, timeout=REQUEST_TIMEOUT_S)
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise WeatherUnavailable(f"Open-Meteo injoignable : {error}") from error

    return response.json().get("hourly", {})


def _same_day_previous_year(day: date, years_back: int) -> date:
    year = day.year - years_back
    try:
        return day.replace(year=year)
    except ValueError:
        # 29 février : l'année cible n'est pas bissextile.
        return day.replace(year=year, day=28)

def get_weather_forecast(
    lat: float,
    lon: float,
    race_date: date,
    today: date | None = None,
) -> WeatherForecast:
    """Outil de l'agent : météo du jour de course, prévision si possible, climatologie sinon."""
    today = today or date.today()
    days_ahead = (race_date - today).days

    if 0 <= days_ahead <= FORECAST_HORIZON_DAYS:
        stats = summarize_hourly(_fetch_day(FORECAST_URL, lat, lon, race_date))
        return WeatherForecast(
            race_date=race_date,
            lat=lat,
            lon=lon,
            stats=stats,
            source="prévision",
            detail=f"prévision Open-Meteo à J-{days_ahead}",
        )

    samples: list[DayStats] = []
    years: list[int] = []
    for years_back in range(1, CLIMATOLOGY_YEARS + 1):
        past_day = _same_day_previous_year(race_date, years_back)
        try:
            samples.append(summarize_hourly(_fetch_day(ARCHIVE_URL, lat, lon, past_day)))
            years.append(past_day.year)
        except WeatherUnavailable:
            continue

    return WeatherForecast(
        race_date=race_date,
        lat=lat,
        lon=lon,
        stats=average_stats(samples),
        source="climatologie",
        detail=f"climatologie, moyenne de {len(years)} années ({min(years)}-{max(years)})",
    )
