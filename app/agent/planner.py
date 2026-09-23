import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from app.agent.state import AgentState
from app.agent.tools import TOOLS

load_dotenv()

PLANNER_MODEL = "gemini-3.6-flash"


class PlannerDecision(BaseModel):
    """Sortie structurée attendue du planner : la prochaine vague d'outils à appeler."""

    next_tools: list[str] = Field(
        description="Noms des outils à appeler ensuite, dans l'ordre. Vide si tout est déjà prêt."
    )
    reasoning: str = Field(description="Justification courte du choix, pour le journal de l'agent.")


def _describe_state(state: AgentState) -> str:
    """Résumé textuel de ce qui est déjà disponible, pour que le LLM ne redemande pas l'acquis."""
    lines = []
    for field in ("route", "segments", "athlete", "gap_model", "weather"):
        status = "disponible" if state.get(field) is not None else "manquant"
        lines.append(f"- {field} : {status}")
    return "\n".join(lines)


def _build_llm() -> ChatGoogleGenerativeAI:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY absente : vérifie ton fichier .env.")
    return ChatGoogleGenerativeAI(model=PLANNER_MODEL, google_api_key=api_key, temperature=0)


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
        "Propose la prochaine vague d'outils à appeler pour compléter les données manquantes. "
        "N'appelle jamais un outil dont le résultat est déjà 'disponible'. "
        "Si tout est disponible, renvoie une liste vide."
    )

    decision = structured_llm.invoke(prompt)

    return {
        **state,
        "pending_tool_calls": decision.next_tools,
    }
