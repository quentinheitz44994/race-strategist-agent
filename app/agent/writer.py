from langchain_google_genai import ChatGoogleGenerativeAI

from app.agent.planner import _build_llm
from app.agent.state import AgentState


def _describe_athlete(state: AgentState) -> str:
    athlete = state.get("athlete")
    if athlete is None:
        return "Profil athlète non disponible."
    warnings = "\n".join(f"  - {w}" for w in athlete.warnings) or "  - aucun"
    return (
        f"- Allure de référence sur plat : {athlete.flat_pace_s_per_km:.0f} s/km\n"
        f"- Exposant d'endurance : {athlete.riegel_exponent:.3f} ({athlete.endurance_rating})\n"
        f"- Source : {athlete.source}\n"
        f"- Avertissements :\n{warnings}"
    )


def _describe_route(state: AgentState) -> str:
    route = state.get("route")
    segments = state.get("segments")
    if route is None or segments is None:
        return "Parcours non disponible."
    lines = [f"- Distance totale : {route.distance_m / 1000:.1f} km, D+ {route.elev_gain_m:.0f} m"]
    for s in segments:
        lines.append(
            f"  - Segment {s.index} ({s.kind}) : {s.distance_m:.0f} m, "
            f"pente moy. {s.avg_slope * 100:.1f} %"
        )
    return "\n".join(lines)


def _describe_weather(state: AgentState) -> str:
    weather = state.get("weather")
    if weather is None:
        return "Météo non disponible."
    return (
        f"- {weather.source} : {weather.detail}\n"
        f"- Température moyenne attendue : {weather.stats.temp_mean_c:.1f} °C\n"
        f"- Précipitations : {weather.stats.precipitation_mm:.1f} mm"
    )


def _describe_gap_model(state: AgentState) -> str:
    gap_model = state.get("gap_model")
    if gap_model is None:
        return "Calibrage GAP non disponible."
    if gap_model.n_activities == 0:
        return f"- {gap_model.source} (aucune calibration personnelle)"
    return (
        f"- Calibré sur {gap_model.n_activities} activité(s) locale(s), "
        f"{gap_model.n_samples} échantillons, RMSE={gap_model.rmse:.3f}"
    )


def run_writer(state: AgentState, llm: ChatGoogleGenerativeAI | None = None) -> AgentState:
    """Rédige le rapport final en Markdown à partir des données déjà calculées, sans en inventer."""
    llm = llm or _build_llm()

    prompt = (
        "Rédige un rapport de stratégie de course en Markdown, en français, à partir "
        "STRICTEMENT des données suivantes. N'invente et ne recalcule aucun chiffre : "
        "reprends exactement ceux fournis ci-dessous.\n\n"
        f"## Profil athlète\n{_describe_athlete(state)}\n\n"
        f"## Parcours\n{_describe_route(state)}\n\n"
        f"## Météo\n{_describe_weather(state)}\n\n"
        f"## Calibrage GAP\n{_describe_gap_model(state)}\n\n"
        "Structure attendue : un titre, un résumé en 2-3 phrases, puis une section par "
        "thème ci-dessus. Mentionne explicitement l'origine de chaque donnée "
        "(saisie, calibrage, prévision ou climatologie)."
    )

    response = llm.invoke(prompt)
    report_md = response.content if hasattr(response, "content") else str(response)

    return {**state, "report_md": report_md}
