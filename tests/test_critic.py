from typing import Literal

from app.agent.critic import CriticVerdict, run_critic
from app.agent.state import AgentState
from app.core.athlete import AthleteProfile
from app.core.models import RouteProfile, Segment, TrackPoint


class FakeLLM:
    def __init__(self, verdict: CriticVerdict):
        self._verdict = verdict

    def with_structured_output(self, schema):
        return self

    def invoke(self, prompt: str) -> CriticVerdict:
        return self._verdict


def _route_et_segments_coherents() -> tuple[RouteProfile, list[Segment]]:
    route = RouteProfile(
        name="test", distance_m=1000.0, elev_gain_m=0.0, elev_loss_m=0.0,
        points=[TrackPoint(lat=0, lon=0, elevation_m=0, distance_m=0)],
    )
    segments = [
        Segment(index=0, start_m=0, end_m=500, distance_m=500, elev_gain_m=0,
                elev_loss_m=0, avg_slope=0, alt_min_m=0, alt_max_m=0, kind="plat"),
        Segment(index=1, start_m=500, end_m=1000, distance_m=500, elev_gain_m=0,
                elev_loss_m=0, avg_slope=0, alt_min_m=0, alt_max_m=0, kind="plat"),
    ]
    return route, segments


def test_segments_incoherents_bloque_sans_appeler_le_llm():
    route, segments = _route_et_segments_coherents()
    segments[1].distance_m = 400  # rend la somme incohérente avec route.distance_m

    state: AgentState = {"route": route, "segments": segments, "athlete": None}
    result = run_critic(state, llm=FakeLLM(CriticVerdict(status="ok", diagnosis="")))

    assert result["critic_status"] == "needs_revision"
    assert "incohérente" in result["critic_diagnosis"]


def test_avertissements_athlete_bloquent_avant_le_llm():
    route, segments = _route_et_segments_coherents()
    athlete = AthleteProfile(
        name="test", weight_kg=70, reference_distance_m=1000, flat_pace_s_per_km=300,
        predicted_time_s=300, riegel_exponent=1.06, riegel_coefficient=0.1,
        endurance_rating="dans la norme", warnings=["Extrapolation excessive"], source="test",
    )
    state: AgentState = {"route": route, "segments": segments, "athlete": athlete}

    result = run_critic(state, llm=FakeLLM(CriticVerdict(status="ok", diagnosis="")))

    assert result["critic_status"] == "needs_revision"
    assert "Extrapolation excessive" in result["critic_diagnosis"]


def test_plan_propre_consulte_le_llm_et_suit_son_verdict():
    route, segments = _route_et_segments_coherents()
    athlete = AthleteProfile(
        name="test", weight_kg=70, reference_distance_m=1000, flat_pace_s_per_km=300,
        predicted_time_s=300, riegel_exponent=1.06, riegel_coefficient=0.1,
        endurance_rating="dans la norme", warnings=[], source="test",
    )
    state: AgentState = {"route": route, "segments": segments, "athlete": athlete}

    result = run_critic(state, llm=FakeLLM(CriticVerdict(status="ok", diagnosis="")))

    assert result["critic_status"] == "ok"
    assert result["critic_diagnosis"] is None
