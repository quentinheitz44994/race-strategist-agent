import sys

from app.core.gpx import load_route
from app.core.segmentation import segment_route

route = load_route(sys.argv[1])
print(f"{route.name} — {route.distance_m / 1000:.1f} km, D+ {route.elev_gain_m:.0f} m, D- {route.elev_loss_m:.0f} m")

for s in segment_route(route):
    print(
        f"  {s.index:2d} | {s.start_m/1000:5.1f}→{s.end_m/1000:5.1f} km "
        f"| {s.avg_slope*100:+5.1f} % | D+ {s.elev_gain_m:4.0f} | {s.kind}"
    )