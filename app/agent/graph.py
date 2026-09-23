from langgraph.graph import END, StateGraph

from app.agent.critic import run_critic
from app.agent.executor import run_tool_executor
from app.agent.planner import run_planner
from app.agent.state import MAX_ITERATIONS, AgentState
from app.agent.writer import run_writer

REQUIRED_FIELDS = (
    "route", "segments", "athlete", "gap_model", "weather", "pacing", "fueling",
)


def _all_data_present(state: AgentState) -> bool:
    return all(state.get(field) is not None for field in REQUIRED_FIELDS)


def _route_after_planner(state: AgentState) -> str:
    """S'il n'y a plus rien à demander, on passe au critic ; sinon on exécute les outils."""
    if not state.get("pending_tool_calls"):
        return "critic"
    return "tool_executor"


def _route_after_executor(state: AgentState) -> str:
    """Inutile de payer un appel LLM juste pour constater qu'il ne manque plus rien."""
    if _all_data_present(state) or state.get("iteration", 0) >= MAX_ITERATIONS:
        return "critic"
    return "planner"


def _route_after_critic(state: AgentState) -> str:
    """Reboucle vers le planner uniquement si des données manquent et restent récupérables."""
    if state.get("critic_status") != "needs_revision":
        return "writer"
    if state.get("iteration", 0) >= MAX_ITERATIONS:
        return "writer"
    if _all_data_present(state):
        # Rien ne manque : replanifier ne corrigerait rien, on rédige avec le diagnostic.
        return "writer"
    return "planner"


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("planner", run_planner)
    graph.add_node("tool_executor", run_tool_executor)
    graph.add_node("critic", run_critic)
    graph.add_node("writer", run_writer)

    graph.set_entry_point("planner")
    graph.add_conditional_edges("planner", _route_after_planner, {
        "tool_executor": "tool_executor",
        "critic": "critic",
    })
    graph.add_conditional_edges("tool_executor", _route_after_executor, {
        "planner": "planner",
        "critic": "critic",
    })
    graph.add_conditional_edges("critic", _route_after_critic, {
        "planner": "planner",
        "writer": "writer",
    })
    graph.add_edge("writer", END)

    return graph.compile()
