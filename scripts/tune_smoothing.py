import sys

import gpxpy
import numpy as np

from app.core.gpx import compute_elevation_change, load_route, smooth_elevation

path = sys.argv[1]

with open(path, "r", encoding="utf-8") as handle:
    gpx = gpxpy.parse(handle)

raw = np.array(
    [p.elevation for t in gpx.tracks for s in t.segments for p in s.points if p.elevation is not None],
    dtype=float,
)

route = load_route(path, smooth_window=1, threshold_m=0.0)
espacement = route.distance_m / len(raw)

print(f"{len(raw)} points, un point tous les {espacement:.1f} m")
print(f"D+ brut, sans lissage ni seuil : {compute_elevation_change(raw, 0.0)[0]:.0f} m\n")

print(f"{'window':>7} {'seuil':>7} {'D+':>8}")
for window in (1, 5, 9, 15, 21, 31):
    lisse = smooth_elevation(raw, window=window)
    for seuil in (0.0, 0.5, 1.0, 2.0):
        gain, _ = compute_elevation_change(lisse, threshold_m=seuil)
        print(f"{window:>7} {seuil:>7.1f} {gain:>8.0f}")