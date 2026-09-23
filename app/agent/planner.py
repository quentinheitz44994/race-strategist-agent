import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from app.agent.state import TOOL_OUTPUT_FIELD, AgentState, ToolCall
from app.agent.tools import TOOLS

load_dotenv()

# Configurable : les noms de modèles Gemini changent souvent, et leurs quotas gratuits
# varient énormément d'un modèle à l'autre (20 req/jour sur les plus récents).
PLANNER_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest")

# Ordre de dépendance des outils : load_route doit précéder ceux qui consomment son résultat.
DEFAULT_TOOL_ORDER = [
    "load_route",
    "segment_route",
    "load_athlete_profile",
    "calibrate_gap_curve",
    "get_weather_forecast",
    "compute_pacing_plan",
    "compute_fueling_plan",
]


class PlannerDecision(BaseModel):
    """Sortie structurée attendue du planner : la prochaine vague d'outils à appeler."""

    next_tools: list[str] = Field(
        description="Noms des outils à appeler ensuite, dans l'ordre. Vide si tout est déjà prêt."
    )
    reasoning: str = Field(description="Justification courte du choix, pour le journal de l'agent.")


def _describe_state(state: AgentState) -> str:
    """Résumé textuel de ce qui est déjà disponible, pour que le LLM ne redemande pas l'acquis."""
    lines = []
    for name in DEFAULT_TOOL_ORDER:
        field = TOOL_OUTPUT_FIELD[name]
        status = "disponible" if state.get(field) is not None else "manquant"
        lines.append(f"- {field} : {status}")
    return "\n".join(lines)


def _default_missing_tools(state: AgentState) -> list[str]:
    """Plan de secours déterministe quand le LLM planificateur est indisponible.

    La séquence des outils est fixe et connue : la perte du LLM ne doit pas empêcher
    de calculer les données, qui elles n'en ont jamais eu besoin.
    """
    return [
        name for name in DEFAULT_TOOL_ORDER if state.get(TOOL_OUTPUT_FIELD[name]) is None
    ]


def _build_llm() -> ChatGoogleGenerativeAI:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY absente : vérifie ton fichier .env.")
    return ChatGoogleGenerativeAI(
        model=PLANNER_MODEL,
        google_api_key=api_key,
        temperature=0,
        # Aucune relance interne : chaque nœud a déjà son propre repli, et une relance
        # ne ferait que doubler l'attente sur un palier gratuit déjà mis en file d'attente.
        max_retries=0,
        # Le palier gratuit peut mettre jusqu'à ~2 min à répondre, même sur un prompt trivial.
        timeout=150,
    )


def run_planner(state: AgentState, llm: ChatGoogleGenerativeAI | None = None) -> AgentState:
    """Décide, via le LLM, quels outils appeler pour la prochaine vague."""
    llm = llm or _build_llm()
    structured_llm = llm.with_structured_output(PlannerDecision)

    tools_description = "\n".join(f"- {t.name} : {t.description}" for t in TOOLS)

    prompt = (
        "Tu planifies l'exécution d'un agent de stratégie de course à pied. "
        "Voici les outils disponibles :\n"
        f"{tools_description}\n\n"
        "Voici ce qui est déjà disponible dans l'état actuel :\n"
        f"{_describe_state(state)}\n\n"
        "Renvoie dans next_tools TOUS les outils marqués 'manquant' ci-dessus, sans exception, "
        "en une seule réponse. Les outils sont exécutés séquentiellement dans l'ordre que tu "
        "donnes, et chacun voit les résultats des précédents : tu peux donc demander un outil "
        "dont la dépendance figure plus haut dans ta propre liste. "
        "Ordre imposé : load_route, segment_route, load_athlete_profile, calibrate_gap_curve, "
        "get_weather_forecast, compute_pacing_plan, compute_fueling_plan — en ne gardant que "
        "ceux marqués 'manquant'. "
        "N'appelle jamais un outil dont le résultat est déjà 'disponible'. "
        "Si tout est disponible, renvoie une liste vide."
    )

    try:
        decision = structured_llm.invoke(prompt)
    except Exception as error:
        # Quota dépassé, réseau coupé, réponse illisible : on cesse de planifier proprement
        # au lieu de faire remonter une erreur brute jusqu'à l'API (NF5).
        log = list(state.get("tool_call_log", []))
        log.append(
            ToolCall(tool_name="planner (LLM)", arguments={}, success=False, error=str(error))
        )
        return {
            **state,
            "pending_tool_calls": _default_missing_tools(state),
            "tool_call_log": log,
        }

    return {
        **state,
        "pending_tool_calls": decision.next_tools,
    }
