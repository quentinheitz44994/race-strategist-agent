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


def _format_hms(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 3600}h{(total % 3600) // 60:02d}"


def _format_pace(pace_s_per_km: float) -> str:
    total = int(round(pace_s_per_km))
    return f"{total // 60}:{total % 60:02d}/km"


def _describe_pacing(state: AgentState) -> str:
    pacing = state.get("pacing")
    if pacing is None:
        return "Plan d'allure non disponible."

    lines = [f"- Temps total estimé : {_format_hms(pacing.total_time_s)}"]
    if pacing.target_time_s:
        statut = "atteint" if pacing.converged else "NON atteint"
        lines.append(f"- Objectif de {_format_hms(pacing.target_time_s)} : {statut}")
    for note in pacing.notes:
        lines.append(f"- {note}")

    lines.append("- Tableau des segments :")
    lines.append("  | Segment | Type | Distance | Allure | Vit. ascens. | Temps | Cumulé |")
    lines.append("  |---|---|---|---|---|---|---|")
    for s in pacing.segments:
        lines.append(
            f"  | {s.index} | {s.kind} | {s.distance_m / 1000:.1f} km | "
            f"{_format_pace(s.pace_s_per_km)} | {s.vertical_speed_m_per_h:.0f} m/h | "
            f"{_format_hms(s.time_s)} | {_format_hms(s.cumulative_time_s)} |"
        )
    return "\n".join(lines)


def _describe_fueling(state: AgentState) -> str:
    fueling = state.get("fueling")
    if fueling is None:
        return "Plan nutrition non disponible."

    lines = [
        f"- Durée retenue : {fueling.duration_h:.1f} h à {fueling.temp_c:.1f} °C "
        f"(intensité {fueling.intensity})",
        f"- Glucides : {fueling.carbs_g_per_h.low:.0f} à {fueling.carbs_g_per_h.high:.0f} g/h "
        f"(total {fueling.total_carbs_g.low:.0f}-{fueling.total_carbs_g.high:.0f} g)",
        f"- Liquide : {fueling.fluid_ml_per_h.low:.0f} à {fueling.fluid_ml_per_h.high:.0f} ml/h "
        f"(total {fueling.total_fluid_ml.low / 1000:.1f}-{fueling.total_fluid_ml.high / 1000:.1f} L)",
        f"- Sodium : {fueling.sodium_mg_per_h.low:.0f} à {fueling.sodium_mg_per_h.high:.0f} mg/h",
    ]
    for note in fueling.notes:
        lines.append(f"- {note}")
    lines.append(f"- AVERTISSEMENT : {fueling.disclaimer}")
    return "\n".join(lines)


def _fallback_report(state: AgentState, reason: str) -> str:
    """Rapport de secours sans LLM : les données brutes, déjà structurées en Markdown."""
    # Les erreurs gRPC font plusieurs centaines de lignes : inutilisable en tête de rapport.
    short_reason = reason.split("\n")[0][:200]
    return (
        "# Rapport de stratégie (mode dégradé)\n\n"
        f"> Le service de rédaction n'était pas disponible ({short_reason}).\n"
        "> Les données ci-dessous sont celles calculées par les outils, sans mise en forme rédigée.\n\n"
        f"## Profil athlète\n{_describe_athlete(state)}\n\n"
        f"## Parcours\n{_describe_route(state)}\n\n"
        f"## Plan d'allure\n{_describe_pacing(state)}\n\n"
        f"## Nutrition et hydratation\n{_describe_fueling(state)}\n\n"
        f"## Météo\n{_describe_weather(state)}\n\n"
        f"## Calibrage GAP\n{_describe_gap_model(state)}\n"
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
        f"## Plan d'allure\n{_describe_pacing(state)}\n\n"
        f"## Nutrition et hydratation\n{_describe_fueling(state)}\n\n"
        f"## Météo\n{_describe_weather(state)}\n\n"
        f"## Calibrage GAP\n{_describe_gap_model(state)}\n\n"
        "Structure attendue : un titre, un résumé en 2-3 phrases donnant le temps cible et "
        "la stratégie générale, puis une section par thème ci-dessus. Reproduis le tableau "
        "des segments tel quel, en Markdown. Mentionne explicitement l'origine de chaque donnée "
        "(saisie, calibrage, prévision ou climatologie), et reprends l'avertissement nutrition."
    )

    try:
        response = llm.invoke(prompt)
    except Exception as error:
        return {**state, "report_md": _fallback_report(state, str(error))}

    report_md = response.content if hasattr(response, "content") else str(response)

    return {**state, "report_md": report_md}
