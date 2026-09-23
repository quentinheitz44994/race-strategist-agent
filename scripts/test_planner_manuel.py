from app.agent.planner import run_planner
from app.agent.state import AgentState

state: AgentState = {
    "gpx_path": "data/Chianti_CUT73.gpx",
    "race_date": "2026-06-20",
    "iteration": 0,
    "tool_call_log": [],
}

result = run_planner(state)  # pas de llm= fourni -> construit le vrai ChatGoogleGenerativeAI
print("Outils proposés :", result["pending_tool_calls"])
