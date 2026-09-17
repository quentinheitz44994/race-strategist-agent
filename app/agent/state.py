from typing import Literal, TypedDict

from app.core.athlete import AthleteProfile
from app.core.gap_calibration import GapModel
from app.core.models import RouteProfile, Segment
from app.core.weather import WeatherForecast

MAX_ITERATIONS = 8


class ToolCall(TypedDict):
    """Trace d'un appel d'outil : sert à alimenter agent_runs (§6.3) et l'UI (US8)."""

    tool_name: str
    arguments: dict
    success: bool
    error: str | None


class AgentState(TypedDict, total=False):
    """État partagé entre les quatre nœuds du graphe (F7)."""

    # Entrée, fixée au départ, jamais réécrite par les nœuds.
    gpx_path: str
    race_date: str  # ISO, ex "2026-06-20"
    target_time_s: float | None
    target_effort: str | None

    # Résultats d'outils, remplis progressivement par le tool executor.
    route: RouteProfile | None
    segments: list[Segment] | None
    athlete: AthleteProfile | None
    gap_model: GapModel | None
    weather: WeatherForecast | None

    # Pilotage de la boucle.
    pending_tool_calls: list[str]
    tool_call_log: list[ToolCall]
    iteration: int

    # Sortie du critic.
    critic_status: Literal["ok", "needs_revision"] | None
    critic_diagnosis: str | None

    # Sortie finale.
    report_md: str | None
