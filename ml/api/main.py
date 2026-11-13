"""Sol Health inference API (FastAPI).

    cd ml && uvicorn api.main:app --reload --port 8000
    open http://localhost:8000/docs

Serves the demo crew from data/demo/ and runs the models in models/.
The `at` query parameter replays the mission at an earlier hour (ISO timestamp),
which lets the frontend animate the timeline without a live data feed.
"""
from __future__ import annotations

import json
from functools import lru_cache

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from sol_ml.config import DEMO_DIR, ALL_SIGNALS, CONDITIONS, CONDITION_LABELS
from sol_ml.engine import HealthEngine, LEVEL_RANK

app = FastAPI(title="Sol Health API", version="1.0.0",
              description="Astronaut health monitoring: vitals, risk assessment, actions, forecasts. "
                          "Synthetic data, decision support only.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@lru_cache
def engine() -> HealthEngine:
    return HealthEngine.load()


@lru_cache
def demo():
    with open(DEMO_DIR / "crew.json") as f:
        meta = json.load(f)
    tel = pd.read_csv(DEMO_DIR / "telemetry.csv", parse_dates=["timestamp"])
    return meta, tel


def _profile(aid: str) -> dict:
    meta, _ = demo()
    for p in meta["crew"]:
        if p["astronaut_id"] == aid:
            return p
    raise HTTPException(404, f"Unknown astronaut_id {aid}")


def _history(aid: str, at: str | None) -> pd.DataFrame:
    _profile(aid)                      # 404 for unknown ids
    _, tel = demo()
    h = tel[tel["astronaut_id"] == aid]
    if at:
        try:
            h = h[h["timestamp"] <= pd.Timestamp(at)]
        except ValueError:
            raise HTTPException(422, "`at` must be an ISO timestamp, e.g. 2026-11-10T14:00:00")
    if len(h) < 24:
        raise HTTPException(422, "Need at least 24 hours of history before `at`")
    return h.drop(columns=["sim_ground_truth"], errors="ignore")


def _json_rows(df: pd.DataFrame) -> list[dict]:
    out = df.copy()
    out["timestamp"] = out["timestamp"].astype(str)
    return out.to_dict(orient="records")


# --------------------------------------------------------------------------- routes
@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/mission")
def mission(at: str | None = None):
    meta, tel = demo()
    end = pd.Timestamp(at) if at else tel["timestamp"].max()
    return {**meta["mission"], "now": str(end), "time_range": {
        "start": str(tel["timestamp"].min()), "end": str(tel["timestamp"].max())}}


@app.get("/api/meta")
def meta_info():
    """Static lists the UI needs: conditions, signals."""
    return {"conditions": [{"id": c, "label": CONDITION_LABELS[c]} for c in CONDITIONS],
            "signals": ALL_SIGNALS, "levels": list(LEVEL_RANK)}


@app.get("/api/crew")
def crew(at: str | None = None):
    """Crew overview: one card per astronaut with current status."""
    meta, _ = demo()
    cards = []
    for p in meta["crew"]:
        a = engine().assess(_history(p["astronaut_id"], at), p)
        cards.append({
            "astronaut_id": p["astronaut_id"], "name": p["name"], "role": p["role"],
            "status": a["status"], "health_score": a["health_score"],
            "condition": a["condition"], "condition_label": a["condition_label"],
            "top_alert": a["alerts"][0]["message"] if a["alerts"] else None,
            "vitals": {k: v["value"] for k, v in a["vitals"].items()},
            "timestamp": a["timestamp"],
        })
    cards.sort(key=lambda c: (-LEVEL_RANK[c["status"]], c["health_score"]))
    return cards


@app.get("/api/crew/{aid}")
def astronaut(aid: str):
    return _profile(aid)


@app.get("/api/crew/{aid}/vitals")
def vitals(aid: str, hours: int = Query(72, ge=1, le=24 * 200), at: str | None = None):
    """Raw hourly telemetry for charts (oldest first)."""
    return _json_rows(_history(aid, at).tail(hours))


@app.get("/api/crew/{aid}/assessment")
def assessment(aid: str, at: str | None = None):
    """Current status, condition probabilities, alerts, what to do now, daily plan."""
    return engine().assess(_history(aid, at), _profile(aid))


@app.get("/api/crew/{aid}/timeline")
def timeline(aid: str, hours: int = Query(72, ge=1, le=24 * 200), at: str | None = None):
    """Hour-by-hour model output for status strips / replay."""
    return engine().timeline(_history(aid, at), _profile(aid), hours)


@app.get("/api/crew/{aid}/forecast")
def forecast(aid: str, horizon_days: int = Query(90, ge=1, le=1000), at: str | None = None):
    """Bone and muscle deconditioning projection, with the effect of meeting the ARED target."""
    return engine().forecast_deconditioning(_profile(aid), _history(aid, at), horizon_days)


@app.get("/api/crew/{aid}/radiation")
def radiation(aid: str, at: str | None = None):
    meta, _ = demo()
    return engine().radiation_status(_profile(aid), _history(aid, at), meta["mission"])


# ---------------------------------------------------------------- bring-your-own data
class Reading(BaseModel):
    timestamp: str
    mission_day: int = 1
    heart_rate: float
    hrv_rmssd: float
    spo2: float
    resp_rate: float
    systolic_bp: float
    diastolic_bp: float
    core_temp: float
    pvt_reaction_ms: float
    activity_level: float = Field(0.2, ge=0, le=1)
    is_asleep: int = 0
    fluid_intake_ml: float = 120
    cabin_co2_mmhg: float = 2.0
    radiation_msv: float = 0.04
    exercise_type: str = "none"


class AssessRequest(BaseModel):
    astronaut_id: str = "custom"
    readings: list[Reading] = Field(..., min_length=6, description="Hourly readings, oldest first")
    baseline: dict | None = Field(None, description="Optional personal baseline per vital")


@app.post("/api/assess")
def assess_custom(req: AssessRequest):
    """Assess any hourly series (e.g. from a wearable feed or a what-if form)."""
    df = pd.DataFrame([r.model_dump() for r in req.readings])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["astronaut_id"] = req.astronaut_id
    profile = {"baseline": req.baseline} if req.baseline else None
    return engine().assess(df, profile)
