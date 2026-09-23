from langgraph.graph import END, StateGraph

from app.agent.critic import run_critic
from app.agent.executor import run_tool_executor
from app.agent.planner import run_planner
from app.agent.state import MAX_ITERATIONS, AgentState
from app.agent.writer import run_writer


def _route_after_planner(state: AgentState) -> str:
    """S'il n'y a plus rien à demander, on passe au critic ; sinon on exécute les outils."""
    if not state.get("pending_tool_calls"):
        return "critic"
    return "tool_executor"


def _route_after_critic(state: AgentState) -> str:
    """Boucle vers le planner en cas d'incohérence, sauf si le budget d'itérations est épuisé."""
    if state.get("critic_status") == "needs_revision" and state.get("iteration", 0) < MAX_ITERATIONS:
        return "planner"
    return "writer"


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
    graph.add_edge("tool_executor", "planner")
    graph.add_conditional_edges("critic", _route_after_critic, {
        "planner": "planner",
        "writer": "writer",
    })
    graph.add_edge("writer", END)

    return graph.compile()
