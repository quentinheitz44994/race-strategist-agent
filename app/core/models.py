from pydantic import BaseModel


class TrackPoint(BaseModel):
    """Un point GPS de la trace."""
    lat: float
    lon: float
    elevation_m: float
    distance_m: float  # distance cumulée depuis le départ


class RouteProfile(BaseModel):
    """Le parcours complet, après parsing et lissage."""
    name: str
    distance_m: float
    elev_gain_m: float
    elev_loss_m: float
    points: list[TrackPoint]


class Segment(BaseModel):
    """Un tronçon homogène du parcours."""
    index: int
    start_m: float
    end_m: float
    distance_m: float
    elev_gain_m: float
    elev_loss_m: float
    avg_slope: float          # pente moyenne en ratio : 0.08 = 8 %
    alt_min_m: float
    alt_max_m: float
    kind: str                 # "montée", "descente" ou "plat"