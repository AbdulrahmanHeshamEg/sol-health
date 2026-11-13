"""Sol Health inference API (FastAPI).

    cd ml && uvicorn api.main:app --reload --port 8000
    open http://localhost:8000/docs

Serves the demo crew from data/demo/ and runs the v2 engine (models/engine_config.json).
The `at` query parameter replays the mission at an earlier hour (ISO timestamp),
which lets the frontend animate the timeline without a live data feed.
All medical logic (status, thresholds, actions, explanations) lives here, never in the frontend.
"""
from __future__ import annotations

import json
import threading
from contextlib import asynccontextmanager
from functools import lru_cache

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from sol_ml import config, indicators as catalogue
from sol_ml.detectors import cabin as cabin_limits
from sol_ml.config import DEMO_DIR, ALL_SIGNALS, ENGINE_CONDITIONS, ENGINE_CONDITION_LABELS
from sol_ml.engine import HealthEngine, LEVEL_RANK, Prepared

MIN_HISTORY_HOURS = 24
# Replay buttons: the moment at which each planted case is worth looking at (the engine has had time to react).
SHOW_AFTER_HOURS = {"cabin_co2": 8 * 24 + 12, "slow_drift": 6 * 24 + 12, "odd_combination": 4 * 24 + 12, "solar_storm": 3}
QUIET_DAY = "2026-09-15 12:00:00"
CITATIONS = [
    "PMData: Thambawita et al., PMData: A Sports Logging Dataset, MMSys 2020, doi:10.1145/3339825.3394926",
    "Data and visualizations are courtesy of the Environmental Data Application (EDA) (https://visualization.osdr.nasa.gov/eda/).",
    "MSL RAD: NASA/JPL, Hassler et al. (Curiosity Radiation Assessment Detector), level-2 data from NASA CDAWeb.",
]

@asynccontextmanager
async def lifespan(_: FastAPI):
    threading.Thread(target=warm_up, daemon=True).start()
    yield


app = FastAPI(title="Sol Health API", version="2.0.0", lifespan=lifespan,
              description="Astronaut health monitoring: indicators, status with a reason, actions, forecasts. "
                          "The crew is simulated (calibrated on real data); decision support only.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@lru_cache
def engine() -> HealthEngine:
    return HealthEngine.load(demo_dir=DEMO_DIR)


@lru_cache
def demo():
    meta = json.loads((DEMO_DIR / "crew.json").read_text())
    tel = pd.read_csv(DEMO_DIR / "telemetry.csv", parse_dates=["timestamp"])
    daily = pd.read_csv(DEMO_DIR / "daily.csv")
    cases = json.loads((DEMO_DIR / "planted_cases.json").read_text()) if (DEMO_DIR / "planted_cases.json").exists() else []
    sources = json.loads((DEMO_DIR / "sources.json").read_text()) if (DEMO_DIR / "sources.json").exists() else {}
    return meta, tel, daily, cases, sources


def _profile(aid: str) -> dict:
    for p in demo()[0]["crew"]:
        if p["astronaut_id"] == aid:
            return p
    raise HTTPException(404, f"Unknown astronaut_id {aid}")


@lru_cache
def _prepared(aid: str) -> Prepared:
    """Causal tables for one astronaut's whole history, computed once. Any earlier hour is read from the same tables."""
    profile = _profile(aid)
    _, tel, daily, _, _ = demo()
    return engine().prepare(tel[tel["astronaut_id"] == aid], profile, daily[daily["astronaut_id"] == aid])


@lru_cache
def _full_timeline(aid: str) -> list[dict]:
    """Hour-by-hour status for the whole mission, computed once (about 2 s per crewmember). Because every table is
    causal, the status at hour i is the same whatever moment is being replayed, so any window is a slice of this."""
    prep = _prepared(aid)
    return engine().timeline(None, prep=prep, end=len(prep.hourly) - 1, hours=len(prep.hourly))


def warm_up():
    """Fill the caches in the background so the first page load does not wait for them."""
    for p in demo()[0]["crew"]:
        _full_timeline(p["astronaut_id"])


def _at(aid: str, at: str | None) -> tuple[Prepared, int]:
    prep = _prepared(aid)
    idx = len(prep.hourly) - 1
    if at:
        try:
            when = pd.Timestamp(at)
        except ValueError:
            raise HTTPException(422, "`at` must be an ISO timestamp, e.g. 2026-11-10T14:00:00")
        idx = int(np.searchsorted(prep.hourly["timestamp"].to_numpy(), when.to_datetime64(), side="right")) - 1
    if idx + 1 < MIN_HISTORY_HOURS:
        raise HTTPException(422, "Need at least 24 hours of history before `at`")
    return prep, idx


def _json_rows(df: pd.DataFrame) -> list[dict]:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].astype(str)
    return json.loads(out.to_json(orient="records"))


# --------------------------------------------------------------------------- routes
@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/mission")
def mission(at: str | None = None):
    meta, tel, _, cases, _ = demo()
    end = pd.Timestamp(at) if at else tel["timestamp"].max()
    return {**meta["mission"], "now": str(end),
            "time_range": {"start": str(tel["timestamp"].min()), "end": str(tel["timestamp"].max())},
            "replay_marks": [{"id": "quiet_day", "label": "A quiet day", "at": QUIET_DAY, "show_at": QUIET_DAY, "astronaut_id": "ALL"}] + [
                {"id": c["id"], "label": c["title"], "at": c["start"], "astronaut_id": c["astronaut_id"],
                 "show_at": str(pd.Timestamp(c["start"]) + pd.Timedelta(hours=SHOW_AFTER_HOURS.get(c["id"], 24)))} for c in cases]}


@app.get("/api/meta")
def meta_info():
    """Static lists the UI needs: conditions, signals, hazards, data sources and citations."""
    return {"conditions": [{"id": c, "label": ENGINE_CONDITION_LABELS[c]} for c in ENGINE_CONDITIONS],
            "signals": ALL_SIGNALS, "levels": list(LEVEL_RANK), "hazards": catalogue.HAZARDS,
            "sources": demo()[4], "citations": CITATIONS, "limits": display_limits()}


def display_limits() -> dict:
    """Reference lines and targets the UI draws. They come from the engine so the frontend holds no thresholds."""
    e = engine()
    return {"cabin_co2_1h_mmhg": cabin_limits.LIMIT_1H_MMHG, "cabin_co2_7d_mmhg": cabin_limits.LIMIT_7D_MMHG,
            "radiation_ratio_elevated": e.spe_yellow, "radiation_ratio_shelter": e.spe_red,
            "career_dose_msv": config.CAREER_RADIATION_LIMIT_MSV, "dose_yellow_share": 0.8,
            "hip_bmd_loss_alert_pct": config.BMD_LOSS_ALERT_PCT, "sleep_target_h": config.SLEEP_TARGET_H,
            "fluid_target_ml": config.DAILY_FLUID_TARGET_ML, "ared_target_min_week": config.ARED_TARGET_MIN_WEEK,
            "aerobic_target_min_week": config.AEROBIC_TARGET_MIN_WEEK}


@app.get("/api/indicators")
def indicators():
    """Explainer cards: why each indicator is measured, how space affects it, when to escalate, prevention."""
    sources = demo()[4]
    return [dict(card, hazard_names=[catalogue.HAZARDS[h] for h in card["hazards"]],
                 sources={k: sources.get({"sleep_hours": "sleep_minutes", "radiation_dose_rate": "radiation_ugy_per_day"}.get(k, k))
                          for k in card["data_keys"] if sources.get({"sleep_hours": "sleep_minutes", "radiation_dose_rate": "radiation_ugy_per_day"}.get(k, k))})
            for card in catalogue.INDICATORS]


@app.get("/api/demo/cases")
def planted_cases():
    """Ground truth of the planted test cases (for the replay buttons and for evaluation; the engine never reads it)."""
    return demo()[3]


@app.get("/api/crew")
def crew(at: str | None = None):
    """Crew overview: one card per astronaut with current status."""
    cards = []
    for p in demo()[0]["crew"]:
        prep, idx = _at(p["astronaut_id"], at)
        a = engine().assess_at(prep, idx)
        cards.append({
            "astronaut_id": p["astronaut_id"], "name": p["name"], "role": p["role"],
            "status": a["status"], "health_score": a["health_score"],
            "condition": a["condition"], "condition_label": a["condition_label"],
            "top_alert": a["alerts"][0]["message"] if a["alerts"] else None,
            "top_reason": a["alerts"][0]["reason"] if a["alerts"] else None,
            "vitals": {k: v["value"] for k, v in a["vitals"].items()},
            "cabin_co2_mmhg": a["context"]["cabin_co2_mmhg"],
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
    prep, idx = _at(aid, at)
    return _json_rows(prep.hourly.iloc[max(0, idx - hours + 1): idx + 1])


@app.get("/api/crew/{aid}/daily")
def daily_rows(aid: str, days: int = Query(30, ge=1, le=1000), at: str | None = None):
    """Daily indicators (resting HR, sleep, mood, fatigue, stress, glucose) with the body models' flags, oldest first."""
    prep, idx = _at(aid, at)
    d = int(prep.day_of_hour[idx])
    if d < 0 or prep.daily is None:
        return []
    rows = prep.daily.iloc[max(0, d - days + 1): d + 1].copy()
    rows["sleep_hours"] = (rows["sleep_minutes"] / 60).round(2)
    flags = prep.body.iloc[max(0, d - days + 1): d + 1]
    for col in ("spike", "drift", "combo"):
        rows[f"flag_{col}"] = flags[col].to_numpy(bool)
    return _json_rows(rows)


@app.get("/api/crew/{aid}/assessment")
def assessment(aid: str, at: str | None = None):
    """Current status with a one-sentence reason per alert, what to do now, daily plan, body systems."""
    prep, idx = _at(aid, at)
    return engine().assess_at(prep, idx)


@app.get("/api/crew/{aid}/timeline")
def timeline(aid: str, hours: int = Query(72, ge=1, le=24 * 200), at: str | None = None):
    """Hour-by-hour status for status strips / replay."""
    _, idx = _at(aid, at)
    return _full_timeline(aid)[max(0, idx - hours + 1): idx + 1]


@app.get("/api/crew/{aid}/forecast")
def forecast(aid: str, horizon_days: int = Query(90, ge=1, le=1000), at: str | None = None):
    """Bone and muscle projection (with the effect of meeting the ARED target) and the exercise fitness trend."""
    prep, idx = _at(aid, at)
    return engine().forecast_deconditioning(_profile(aid), prep.hourly.iloc[: idx + 1], horizon_days)


@app.get("/api/crew/{aid}/radiation")
def radiation(aid: str, at: str | None = None):
    prep, idx = _at(aid, at)
    return engine().radiation_status(_profile(aid), None, demo()[0]["mission"], prep=prep, end=idx)


@app.get("/api/crew/{aid}/reminders")
def reminders(aid: str, at: str | None = None):
    """Measurements that are due now or later today, plus the check-in streak (prompts and gamification)."""
    prep, idx = _at(aid, at)
    now = prep.hourly["timestamp"].iloc[idx]
    day = int(prep.hourly["mission_day"].iloc[idx])
    today = prep.daily[pd.to_datetime(prep.daily["date"]) == now.normalize()] if prep.daily is not None else pd.DataFrame()
    items = []
    for item in catalogue.SCHEDULE:
        if day % item["every_days"]:
            continue
        logged = bool(len(today) and item["tracked_by"] and pd.notna(today[item["tracked_by"]].iloc[0]) and now.hour >= item["due_hour"])
        status = "done" if logged else "due" if now.hour >= item["due_hour"] else "upcoming"
        items.append({"id": item["id"], "label": item["label"], "due_at": str(now.normalize() + pd.Timedelta(hours=item["due_hour"])),
                      "status": status, "logged_automatically": item["tracked_by"] is not None})
    d = int(prep.day_of_hour[idx])
    streak = 0
    if d >= 0:
        done = prep.daily["fatigue"].notna().to_numpy()[: d + 1]
        while streak <= d and done[d - streak]:
            streak += 1
    return {"now": str(now), "items": items, "checkin_streak_days": streak,
            "due_count": sum(i["status"] == "due" for i in items)}


# ---------------------------------------------------------------- bring-your-own data and the check-in form
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
    radiation_msv: float = 0.02
    exercise_type: str = "none"


class CheckIn(BaseModel):
    """A manual measurement check-in. Every field is optional; only the ones given replace the latest values."""
    systolic_bp: float | None = Field(None, ge=50, le=260)
    diastolic_bp: float | None = Field(None, ge=30, le=160)
    heart_rate: float | None = Field(None, ge=25, le=230)
    spo2: float | None = Field(None, ge=50, le=100)
    core_temp: float | None = Field(None, ge=33, le=43)
    blood_glucose_mg_dl: float | None = Field(None, ge=20, le=600)
    sleep_hours: float | None = Field(None, ge=0, le=16)
    mood: int | None = Field(None, ge=1, le=5)
    stress: int | None = Field(None, ge=1, le=5)
    fatigue: int | None = Field(None, ge=1, le=5)
    headache: bool | None = None


class AssessRequest(BaseModel):
    astronaut_id: str = "custom"
    readings: list[Reading] | None = Field(None, min_length=6, description="Hourly readings, oldest first")
    baseline: dict | None = Field(None, description="Optional personal baseline per vital")
    checkin: CheckIn | None = Field(None, description="Manual check-in applied on top of a demo astronaut's history")
    at: str | None = None


HOURLY_FIELDS = ("systolic_bp", "diastolic_bp", "heart_rate", "spo2", "core_temp")
DAILY_FIELDS = ("blood_glucose_mg_dl", "mood", "stress", "fatigue")


@app.post("/api/assess")
def assess_custom(req: AssessRequest):
    """Two uses. (1) `readings`: assess any hourly series (wearable feed, what-if form).
    (2) `astronaut_id` of a demo crewmember + `checkin`: apply a manual check-in to that person's latest values and
    return the new assessment. Nothing is stored."""
    if req.readings:
        df = pd.DataFrame([r.model_dump() for r in req.readings])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["astronaut_id"] = req.astronaut_id
        return engine().assess(df, {"baseline": req.baseline} if req.baseline else None)
    if req.checkin is None:
        raise HTTPException(422, "Send `readings`, or the `astronaut_id` of a crewmember with a `checkin`")
    prep, idx = _at(req.astronaut_id, req.at)
    given = req.checkin.model_dump(exclude_none=True)
    hourly = prep.hourly.iloc[: idx + 1].copy()
    for k in HOURLY_FIELDS:
        if k in given:
            hourly.loc[hourly.index[-1], k] = float(given[k])
    if any(k in given for k in HOURLY_FIELDS):
        hourly.loc[hourly.index[-1], "activity_level"] = min(float(hourly["activity_level"].iloc[-1]), 0.15)   # taken at rest
    d = int(prep.day_of_hour[idx])
    daily = prep.daily.iloc[: max(d, 0) + 1].copy()
    for k in DAILY_FIELDS:
        if k in given:
            daily.loc[daily.index[-1], k] = float(given[k])
    if "sleep_hours" in given:
        daily.loc[daily.index[-1], "sleep_minutes"] = given["sleep_hours"] * 60
    if "headache" in given:
        daily.loc[daily.index[-1], "headache"] = int(given["headache"])
    result = engine().assess(hourly, prep.profile, daily)
    result["checkin_applied"] = given
    return result
