import tempfile
from pathlib import Path

from fastapi import FastAPI, Form, UploadFile
from pydantic import BaseModel

from app.agent.graph import build_graph

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


class ToolCallOut(BaseModel):
    tool_name: str
    success: bool
    error: str | None


class PlanResponse(BaseModel):
    report_md: str
    tool_calls: list[ToolCallOut]


@app.post("/plan", response_model=PlanResponse)
async def generate_plan(
    gpx: UploadFile,
    race_date: str = Form(...),
    target_time_s: float | None = Form(None),
) -> PlanResponse:
    """Lance l'agent complet sur un GPX uploadé et renvoie le rapport + le journal d'outils."""
    with tempfile.NamedTemporaryFile(suffix=".gpx", delete=False) as tmp:
        tmp.write(await gpx.read())
        tmp_path = tmp.name

    try:
        graph = build_graph()
        initial_state = {
            "gpx_path": tmp_path,
            "race_date": race_date,
            "target_time_s": target_time_s,
            "target_effort": None,
            "iteration": 0,
            "pending_tool_calls": [],
            "tool_call_log": [],
        }
        result = graph.invoke(initial_state)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return PlanResponse(
        report_md=result.get("report_md") or "",
        tool_calls=[
            ToolCallOut(tool_name=c["tool_name"], success=c["success"], error=c["error"])
            for c in result.get("tool_call_log", [])
        ],
    )
