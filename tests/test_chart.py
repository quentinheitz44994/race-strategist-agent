from app.core.chart import render_elevation_profile, segment_color
from app.core.models import RouteProfile, Segment, TrackPoint


def test_segment_color_est_coherente_et_stable():
    assert segment_color("montée") == segment_color("montée")
    assert segment_color("montée") != segment_color("descente")
    assert segment_color("plat") != segment_color("montée")


def test_segment_color_a_un_repli_pour_un_type_inconnu():
    assert segment_color("inconnu") == "#999999"


def test_render_elevation_profile_produit_un_fichier_png_valide(tmp_path):
    route = RouteProfile(
        name="test", distance_m=1000.0, elev_gain_m=50.0, elev_loss_m=0.0,
        points=[
            TrackPoint(lat=0, lon=0, elevation_m=100, distance_m=0),
            TrackPoint(lat=0, lon=0, elevation_m=150, distance_m=1000),
        ],
    )
    segments = [
        Segment(index=0, start_m=0, end_m=1000, distance_m=1000, elev_gain_m=50,
                elev_loss_m=0, avg_slope=0.05, alt_min_m=100, alt_max_m=150, kind="montée"),
    ]
    output = tmp_path / "profil.png"

    render_elevation_profile(route, segments, str(output))

    assert output.exists()
    assert output.read_bytes().startswith(b"\x89PNG")
