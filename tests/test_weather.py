from datetime import date

import pytest

from app.core import weather
from app.core.weather import (
    DayStats,
    WeatherUnavailable,
    average_stats,
    get_weather_forecast,
    summarize_hourly,
)


def _hourly(temps, humidity=None, precipitation=None, wind=None):
    n = len(temps)
    return {
        "temperature_2m": temps,
        "relative_humidity_2m": humidity if humidity is not None else [50.0] * n,
        "precipitation": precipitation if precipitation is not None else [0.0] * n,
        "wind_speed_10m": wind if wind is not None else [10.0] * n,
    }


def test_agregation_horaire():
    stats = summarize_hourly(_hourly([10.0, 20.0, 15.0]))
    assert stats.temp_min_c == 10.0
    assert stats.temp_max_c == 20.0
    assert stats.temp_mean_c == pytest.approx(15.0)


def test_heures_sans_mesure_sont_ignorees():
    stats = summarize_hourly(_hourly([10.0, None, 20.0]))
    assert stats.temp_mean_c == pytest.approx(15.0)


def test_serie_sans_temperature_leve_une_erreur():
    with pytest.raises(WeatherUnavailable):
        summarize_hourly(_hourly([None, None]))


def test_moyenne_climatologique():
    froide = DayStats(
        temp_min_c=5, temp_max_c=15, temp_mean_c=10,
        humidity_mean_pct=60, precipitation_mm=0, wind_max_kmh=10,
    )
    chaude = DayStats(
        temp_min_c=7, temp_max_c=21, temp_mean_c=14,
        humidity_mean_pct=80, precipitation_mm=4, wind_max_kmh=20,
    )
    moyenne = average_stats([froide, chaude])
    assert moyenne.temp_mean_c == pytest.approx(12.0)
    assert moyenne.precipitation_mm == pytest.approx(2.0)


def test_course_proche_utilise_la_prevision(monkeypatch):
    urls = []

    def faux_fetch(url, lat, lon, day):
        urls.append(url)
        return _hourly([12.0, 18.0])

    monkeypatch.setattr(weather, "_fetch_day", faux_fetch)
    prevision = get_weather_forecast(43.5, 11.3, date(2026, 6, 20), today=date(2026, 6, 15))

    assert prevision.source == "prévision"
    assert urls == [weather.FORECAST_URL]
    assert "J-5" in prevision.detail


def test_course_lointaine_bascule_en_climatologie(monkeypatch):
    annees = []

    def faux_fetch(url, lat, lon, day):
        annees.append(day.year)
        return _hourly([12.0, 18.0])

    monkeypatch.setattr(weather, "_fetch_day", faux_fetch)
    prevision = get_weather_forecast(43.5, 11.3, date(2026, 6, 20), today=date(2026, 1, 10))

    assert prevision.source == "climatologie"
    assert annees == [2025, 2024, 2023, 2022, 2021]
    assert "2021-2025" in prevision.detail
