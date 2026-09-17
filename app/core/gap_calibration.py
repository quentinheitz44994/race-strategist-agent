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

import hashlib
import logging
from pathlib import Path

from app.core.activity import extract_slope_speed_pairs, load_activity_gpx

logger = logging.getLogger(__name__)


def _file_hash(path: Path) -> str:
    """Hash du contenu, pas du nom : un fichier renommé reste reconnu."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_activity_pairs(path: Path) -> list[tuple[float, float]] | None:
    """Lit une activité et en extrait les couples (pente, vitesse). None si illisible."""
    if path.suffix.lower() != ".gpx":
        logger.info("Format non géré pour l'instant, ignoré : %s", path.name)
        return None

    try:
        points = load_activity_gpx(str(path))
    except (ValueError, Exception) as error:  # gpxpy peut lever plusieurs types d'erreurs
        logger.warning("Activité illisible, ignorée : %s (%s)", path.name, error)
        return None

    return extract_slope_speed_pairs(points)

def calibrate_gap_curve(activities_dir: str = "data/activities") -> GapModel:
    """Outil de l'agent : calibre le GAP sur les activités locales, replie sur Minetti sinon."""
    directory = Path(activities_dir)

    if not directory.is_dir():
        return _fallback_model(f"dossier introuvable : {activities_dir}")

    seen_hashes: set[str] = set()
    activity_pairs: list[list[tuple[float, float]]] = []
    skipped = 0

    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue

        file_hash = _file_hash(path)
        if file_hash in seen_hashes:
            logger.info("Doublon ignoré : %s", path.name)
            continue
        seen_hashes.add(file_hash)

        pairs = _read_activity_pairs(path)
        if pairs is None:
            skipped += 1
            continue

        activity_pairs.append(pairs)

    if not activity_pairs:
        return _fallback_model("aucune activité exploitable dans le dossier")

    try:
        return build_gap_model(activity_pairs, source=f"{len(activity_pairs)} activités locales")
    except ValueError as error:
        return _fallback_model(f"calibrage impossible ({error})")


def _fallback_model(reason: str) -> GapModel:
    """Repli théorique : aucune correction empirique, Minetti sert de référence directe."""
    logger.info("Repli sur Minetti théorique : %s", reason)
    return GapModel(
        n_activities=0,
        n_samples=0,
        flat_speed_m_s=0.0,
        empirical_factor={},
        theoretical_factor={},
        rmse=0.0,
        source=f"théorique (Minetti) — {reason}",
    )
