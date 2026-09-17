def energy_cost(slope: float) -> float:
    """Coût énergétique de la course en pente, en J/kg/m (Minetti et al., 2002)."""
    i = max(-0.45, min(0.45, slope))
    return (
        155.4 * i**5
        - 30.4 * i**4
        - 43.3 * i**3
        + 46.3 * i**2
        + 19.5 * i
        + 3.6
    )


FLAT_COST = 3.6


def gap_factor(slope: float) -> float:
    """Combien de fois la pente coûte plus cher que le plat."""
    return energy_cost(slope) / FLAT_COST


def adjusted_pace_s_per_km(
    flat_pace_s_per_km: float,
    slope: float,
    walk_slope_threshold: float = 0.20,
    walk_pace_s_per_km: float = 750.0,
) -> float:
    """Allure attendue sur un segment, à partir de l'allure de référence sur plat."""
    pace = flat_pace_s_per_km * gap_factor(slope)
    if slope >= walk_slope_threshold:
        pace = max(pace, walk_pace_s_per_km)
    return pace