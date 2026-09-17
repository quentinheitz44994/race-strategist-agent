from typing import Any

from app.agent.state import AgentState, ToolCall
from app.agent.tools import get_tool


class ToolArgumentsMissing(RuntimeError):
    """Un outil a été demandé alors qu'une dépendance requise n'est pas encore dans l'état."""


def _resolve_arguments(tool_name: str, state: AgentState) -> dict[str, Any]:
    """Construit les arguments d'un outil à partir de ce qui est déjà connu dans l'état.

    C'est la seule fonction qui doit connaître le lien entre le nom d'un outil et
    l'endroit où trouver ses arguments dans l'état — tout le reste du module l'ignore.
    """
    if tool_name == "load_route":
        return {"source": state["gpx_path"]}

    if tool_name == "segment_route":
        if state.get("route") is None:
            raise ToolArgumentsMissing("segment_route nécessite 'route', pas encore chargée.")
        return {"route": state["route"]}

    if tool_name == "load_athlete_profile":
        if state.get("route") is None:
            raise ToolArgumentsMissing("load_athlete_profile nécessite 'route' pour la distance cible.")
        return {"reference_distance_m": state["route"].distance_m}

    if tool_name == "calibrate_gap_curve":
        return {}

    if tool_name == "get_weather_forecast":
        if state.get("route") is None:
            raise ToolArgumentsMissing("get_weather_forecast nécessite 'route' pour la position de départ.")
        depart = state["route"].points[0]
        return {
            "lat": depart.lat,
            "lon": depart.lon,
            "race_date": state["race_date"],
        }

    raise KeyError(f"Pas de règle de résolution d'arguments pour l'outil : {tool_name}")


_STATE_FIELD_BY_TOOL = {
    "load_route": "route",
    "segment_route": "segments",
    "load_athlete_profile": "athlete",
    "calibrate_gap_curve": "gap_model",
    "get_weather_forecast": "weather",
}


def run_tool_executor(state: AgentState) -> AgentState:
    """Exécute les outils en attente, journalise chaque appel, range les résultats dans l'état."""
    pending = list(state.get("pending_tool_calls", []))
    log = list(state.get("tool_call_log", []))

    # Initialisé avec les valeurs déjà connues : garantit que chaque champ de sortie
    # existe toujours dans le résultat, même quand son outil n'a pas (encore) réussi.
    updates: dict[str, Any] = {
        field: state.get(field) for field in set(_STATE_FIELD_BY_TOOL.values())
    }

    for tool_name in pending:
        arguments: dict[str, Any] = {}
        try:
            arguments = _resolve_arguments(tool_name, {**state, **updates})
            tool = get_tool(tool_name)
            result = tool.func(**arguments)

            field = _STATE_FIELD_BY_TOOL[tool_name]
            updates[field] = result
            log.append(ToolCall(tool_name=tool_name, arguments=arguments, success=True, error=None))

        except Exception as error:  # un outil qui échoue ne doit pas casser les suivants
            log.append(
                ToolCall(tool_name=tool_name, arguments=arguments, success=False, error=str(error))
            )

    return {
        **state,
        **updates,
        "tool_call_log": log,
        "pending_tool_calls": [],
        "iteration": state.get("iteration", 0) + 1,
    }
