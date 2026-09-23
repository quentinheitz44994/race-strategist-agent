from app.agent.planner import PlannerDecision, run_planner
from app.agent.state import AgentState


class FakeLLM:
    """Simule un ChatGoogleGenerativeAI : mêmes méthodes, aucun appel réseau."""

    def __init__(self, decision: PlannerDecision):
        self._decision = decision

    def with_structured_output(self, schema):
        return self

    def invoke(self, prompt: str) -> PlannerDecision:
        self.last_prompt = prompt
        return self._decision


def test_planner_propose_load_route_quand_rien_n_est_disponible():
    decision = PlannerDecision(next_tools=["load_route"], reasoning="rien n'est encore chargé")
    fake_llm = FakeLLM(decision)

    state: AgentState = {
        "gpx_path": "data/Chianti_CUT73.gpx",
        "race_date": "2026-06-20",
        "iteration": 0,
        "tool_call_log": [],
    }

    result = run_planner(state, llm=fake_llm)

    assert result["pending_tool_calls"] == ["load_route"]
    assert "route : manquant" in fake_llm.last_prompt
    assert "load_route" in fake_llm.last_prompt


def test_planner_ne_redemande_rien_si_tout_est_pret():
    decision = PlannerDecision(next_tools=[], reasoning="tout est prêt")
    fake_llm = FakeLLM(decision)

    state: AgentState = {
        "gpx_path": "data/Chianti_CUT73.gpx",
        "race_date": "2026-06-20",
        "iteration": 3,
        "tool_call_log": [],
        "route": object(),
        "segments": object(),
        "athlete": object(),
        "gap_model": object(),
        "weather": object(),
    }

    result = run_planner(state, llm=fake_llm)

    assert result["pending_tool_calls"] == []
    assert "route : disponible" in fake_llm.last_prompt
