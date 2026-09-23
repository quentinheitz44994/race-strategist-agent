from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app


class FakeGraph:
    def invoke(self, state):
        return {
            "report_md": "# Rapport factice",
            "tool_call_log": [
                {"tool_name": "load_route", "arguments": {}, "success": True, "error": None},
            ],
        }


def test_generate_plan_retourne_le_rapport_et_le_journal(monkeypatch, tmp_path):
    monkeypatch.setattr(main_module, "build_graph", lambda: FakeGraph())

    gpx_path = tmp_path / "test.gpx"
    gpx_path.write_text("<gpx></gpx>", encoding="utf-8")

    client = TestClient(app)
    with open(gpx_path, "rb") as f:
        response = client.post(
            "/plan",
            files={"gpx": ("test.gpx", f, "application/gpx+xml")},
            data={"race_date": "2026-06-20"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["report_md"] == "# Rapport factice"
    assert body["tool_calls"][0]["tool_name"] == "load_route"


def test_health_endpoint_toujours_disponible():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
