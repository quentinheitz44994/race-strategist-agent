from typing import Literal


from app.agent.state import AgentState
from app.core.models import Segment


def _segments_couvrent_le_parcours(route_distance_m: float, segments: list[Segment]) -> str | None:
    """Vérifie la contrainte du F2 : les segments sont contigus et couvrent tout le parcours."""
    if not segments:
        return "Aucun segment produit."

    total = sum(s.distance_m for s in segments)
    if abs(total - route_distance_m) > 1.0:  # tolérance d'1 m pour l'arrondi flottant
        return (
            f"Somme des segments ({total:.1f} m) incohérente avec la distance totale "
            f"du parcours ({route_distance_m:.1f} m)."
        )

    for previous, current in zip(segments, segments[1:]):
        if abs(previous.end_m - current.start_m) > 1.0:
            return f"Trou ou chevauchement entre les segments {previous.index} et {current.index}."

    return None


def run_deterministic_checks(state: AgentState) -> list[str]:
    """Vérifications qui ne nécessitent aucun jugement qualitatif : arithmétique pure."""
    problems: list[str] = []

    route = state.get("route")
    segments = state.get("segments")
    if route is not None and segments is not None:
        issue = _segments_couvrent_le_parcours(route.distance_m, segments)
        if issue:
            problems.append(issue)

    athlete = state.get("athlete")
    if athlete is not None and athlete.warnings:
        problems.append(
            f"Profil athlète avec {len(athlete.warnings)} avertissement(s) : "
            + " ; ".join(athlete.warnings)
        )

    return problems

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from app.agent.planner import PLANNER_MODEL, _build_llm


class CriticVerdict(BaseModel):
    """Jugement qualitatif du critic sur la plausibilité globale du plan."""

    status: Literal["ok", "needs_revision"] = Field(
        description="'ok' si le plan est défendable, 'needs_revision' sinon."
    )
    diagnosis: str = Field(description="Explication courte, vide si status='ok'.")


def _build_qualitative_prompt(state: AgentState) -> str:
    athlete = state["athlete"]
    return (
        "Tu es le contrôle qualité d'un plan de course à pied. Voici le profil de l'athlète :\n"
        f"- Exposant d'endurance : {athlete.riegel_exponent:.3f} ({athlete.endurance_rating})\n"
        f"- Allure de référence sur plat : {athlete.flat_pace_s_per_km:.0f} s/km\n"
        f"- Distance visée : {athlete.reference_distance_m / 1000:.1f} km\n\n"
        "Ce plan est-il globalement plausible compte tenu de ce profil ? "
        "Réponds 'needs_revision' uniquement en cas de doute sérieux, pas pour une nuance mineure."
    )


def run_critic(state: AgentState, llm: ChatGoogleGenerativeAI | None = None) -> AgentState:
    """Vérifie la cohérence du plan : d'abord en pur Python, puis un jugement qualitatif du LLM."""
    problems = run_deterministic_checks(state)

    if problems:
        return {
            **state,
            "critic_status": "needs_revision",
            "critic_diagnosis": " | ".join(problems),
        }

    if state.get("athlete") is None:
        # Rien à juger qualitativement sans profil athlète : on ne bloque pas pour autant.
        return {**state, "critic_status": "ok", "critic_diagnosis": None}

    llm = llm or _build_llm()
    structured_llm = llm.with_structured_output(CriticVerdict)
    verdict = structured_llm.invoke(_build_qualitative_prompt(state))

    return {
        **state,
        "critic_status": verdict.status,
        "critic_diagnosis": verdict.diagnosis or None,
    }

