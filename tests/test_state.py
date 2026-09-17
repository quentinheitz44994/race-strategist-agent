from app.agent.state import AgentState, MAX_ITERATIONS


def test_etat_initial_minimal_est_valide():
    state: AgentState = {
        "gpx_path": "data/Chianti_CUT73.gpx",
        "race_date": "2026-06-20",
        "target_time_s": 36000.0,
        "target_effort": None,
        "iteration": 0,
        "pending_tool_calls": [],
        "tool_call_log": [],
    }
    assert state["iteration"] == 0
    assert state["iteration"] < MAX_ITERATIONS
