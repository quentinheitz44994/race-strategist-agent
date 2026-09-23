import matplotlib
matplotlib.use("Agg")  # rendu sans écran : indispensable en conteneur/serveur, sans affichage.

import matplotlib.pyplot as plt

from app.core.models import RouteProfile, Segment

SEGMENT_COLORS = {
    "montée": "#d9534f",
    "descente": "#5cb85c",
    "plat": "#bbbbbb",
}


def segment_color(kind: str) -> str:
    """Couleur associée à un type de segment, cohérente sur tout le rapport."""
    return SEGMENT_COLORS.get(kind, "#999999")


def render_elevation_profile(route: RouteProfile, segments: list[Segment], output_path: str) -> None:
    """Trace le profil altimétrique, avec un bandeau de couleur par type de segment."""
    distances_km = [p.distance_m / 1000 for p in route.points]
    elevations = [p.elevation_m for p in route.points]

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(distances_km, elevations, color="#333333", linewidth=1.2)

    for segment in segments:
        ax.axvspan(
            segment.start_m / 1000,
            segment.end_m / 1000,
            color=segment_color(segment.kind),
            alpha=0.25,
        )

    ax.set_xlabel("Distance (km)")
    ax.set_ylabel("Altitude (m)")
    ax.set_title("Profil altimétrique")
    fig.tight_layout()
    fig.savefig(output_path, dpi=120)
    plt.close(fig)
