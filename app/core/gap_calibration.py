from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel

from app.core.gap import gap_factor

# Bins de pente : bornes en ratio (0.08 = 8 %), pas de 4 points de pourcentage.
SLOPE_BIN_EDGES = np.arange(-0.28, 0.32, 0.04)
MIN_SAMPLES_PER_BIN = 20
FLAT_BIN_LABEL = "0"


@dataclass
class BinStats:
    """Statistiques agrégées pour une tranche de pente."""

    slope_center: float
    n_samples: int
    median_speed_m_s: float


class GapModel(BaseModel):
    """Courbe de correction GAP calibrée empiriquement, comparée à Minetti."""

    n_activities: int
    n_samples: int
    flat_speed_m_s: float
    empirical_factor: dict[str, float]   # pente (str, ex "0.08") -> facteur empirique
    theoretical_factor: dict[str, float]  # même pente -> gap_factor() théorique
    rmse: float
    source: str

def _bin_label(slope_center: float) -> str:
    return f"{slope_center:.2f}"


def aggregate_by_slope(pairs: list[tuple[float, float]]) -> list[BinStats]:
    """Regroupe les couples (pente, vitesse) de toutes les activités par tranche de pente."""
    if not pairs:
        return []

    slopes = np.array([p[0] for p in pairs])
    speeds = np.array([p[1] for p in pairs])

    bin_indices = np.digitize(slopes, SLOPE_BIN_EDGES)
    stats: list[BinStats] = []

    for bin_index in np.unique(bin_indices):
        mask = bin_indices == bin_index
        if mask.sum() < MIN_SAMPLES_PER_BIN:
            continue

        stats.append(
            BinStats(
                slope_center=float(np.mean(slopes[mask])),
                n_samples=int(mask.sum()),
                median_speed_m_s=float(np.median(speeds[mask])),
            )
        )

    return stats


def build_gap_model(
    activity_pairs: list[list[tuple[float, float]]],
    source: str,
) -> GapModel:
    """Construit le modèle GAP empirique à partir des couples (pente, vitesse) de N activités."""
    all_pairs = [pair for activity in activity_pairs for pair in activity]
    bins = aggregate_by_slope(all_pairs)

    if not bins:
        raise ValueError("Aucun bin de pente n'a assez d'échantillons pour calibrer.")

    flat_candidates = [b for b in bins if abs(b.slope_center) < 0.02]
    if not flat_candidates:
        raise ValueError("Aucune donnée sur terrain plat : impossible d'établir la référence.")
    flat_speed = flat_candidates[0].median_speed_m_s

    empirical: dict[str, float] = {}
    theoretical: dict[str, float] = {}
    squared_errors: list[float] = []

    for b in bins:
        empirical_factor = flat_speed / b.median_speed_m_s
        theoretical_value = gap_factor(b.slope_center)

        empirical[_bin_label(b.slope_center)] = empirical_factor
        theoretical[_bin_label(b.slope_center)] = theoretical_value
        squared_errors.append((empirical_factor - theoretical_value) ** 2)

    return GapModel(
        n_activities=len(activity_pairs),
        n_samples=len(all_pairs),
        flat_speed_m_s=flat_speed,
        empirical_factor=empirical,
        theoretical_factor=theoretical,
        rmse=float(np.sqrt(np.mean(squared_errors))),
        source=source,
    )
