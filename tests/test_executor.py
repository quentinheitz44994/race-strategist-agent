from datetime import date

from app.agent.executor import ToolArgumentsMissing, _resolve_arguments, run_tool_executor
from app.agent.state import AgentState
from app.core.models import RouteProfile, TrackPoint

import pytest


def _route_minimale() -> RouteProfile:
    return RouteProfile(
        name="test",
        distance_m=10_000.0,
        elev_gain_m=100.0,
        elev_loss_m=100.0,
        points=[
            TrackPoint(lat=43.5, lon=11.3, elevation_m=100.0, distance_m=0.0),
            TrackPoint(lat=43.6, lon=11.3, elevation_m=150.0, distance_m=10_000.0),
        ],
    )


def test_resolve_arguments_leve_une_erreur_si_dependance_manquante():
    with pytest.raises(ToolArgumentsMissing):
        _resolve_arguments("segment_route", {"route": None})


def test_resolve_arguments_fonctionne_une_fois_la_dependance_presente():
    route = _route_minimale()
    args = _resolve_arguments("segment_route", {"route": route})
    assert args == {"route": route}


def test_executor_execute_deux_outils_dependants_dans_le_meme_lot(tmp_path):
    # Un GPX minimal réel, pour que load_route -> segment_route s'enchaîne vraiment.
    gpx_content = """<?xml version="1.0"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
  <trk><trkseg>
    <trkpt lat="43.500" lon="11.300"><ele>100</ele></trkpt>
    <trkpt lat="43.510" lon="11.300"><ele>150</ele></trkpt>
    <trkpt lat="43.520" lon="11.300"><ele>120</ele></trkpt>
  </trkseg></trk>
</gpx>"""
    gpx_path = tmp_path / "test.gpx"
    gpx_path.write_text(gpx_content, encoding="utf-8")

    state: AgentState = {
        "gpx_path": str(gpx_path),
        "race_date": "2026-06-20",
        "pending_tool_calls": ["load_route", "segment_route"],
        "tool_call_log": [],
        "iteration": 0,
    }

    result = run_tool_executor(state)

    assert result["route"] is not None
    assert result["segments"] is not None
    assert len(result["tool_call_log"]) == 2
    assert all(call["success"] for call in result["tool_call_log"])
    assert result["iteration"] == 1
    assert result["pending_tool_calls"] == []


def test_executor_journalise_un_echec_sans_planter_les_autres():
    state: AgentState = {
        "gpx_path": "chemin/inexistant.gpx",
        "race_date": "2026-06-20",
        "pending_tool_calls": ["load_route", "calibrate_gap_curve"],
        "tool_call_log": [],
        "iteration": 0,
    }

    result = run_tool_executor(state)

    assert result["route"] is None
    assert result["gap_model"] is not None  # celui-ci ne dépend pas de route, doit réussir
    log_by_name = {call["tool_name"]: call for call in result["tool_call_log"]}
    assert log_by_name["load_route"]["success"] is False
    assert log_by_name["calibrate_gap_curve"]["success"] is True
