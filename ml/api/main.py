"""Sol Health inference API (FastAPI).

    cd ml && uvicorn api.main:app --reload --port 8000
    open http://localhost:8000/docs

Serves the demo astronaut from data/demo/ and runs the v2 engine (models/engine_config.json).
The app is personal: `/api/me` names the astronaut, and every per-person route takes that id.
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

import base64

from fastapi.responses import FileResponse

from sol_ml import brief as daily_brief, config, indicators as catalogue, questions as qbank
from sol_ml import fundus as fundus_rules
from sol_ml.userdata import UserStore
from sol_ml.detectors import cabin as cabin_limits
from sol_ml.config import DEMO_DIR, ALL_SIGNALS, ENGINE_CONDITIONS, ENGINE_CONDITION_LABELS
from sol_ml.engine import HealthEngine, LEVEL_RANK, Prepared

MIN_HISTORY_HOURS = 24
USER = UserStore(config.DATA_DIR / "user")            # the astronaut's own answers and eye photos (git-ignored)
EYE_EXAM_EVERY_DAYS = 30
# Replay buttons: the moment at which each planted case is worth looking at (the engine has had time to react).
SHOW_AFTER_HOURS = {"cabin_co2": 8 * 24 + 12, "slow_drift": 7 * 24 + 12, "odd_combination": 12, "solar_storm": 3}
QUIET_DAY = "2026-09-15 12:00:00"
# What the app opens on: an ordinary working day with the common, well-known problems of a long mission
# (a mood and stress dip, an unusual mix of signals, an early optic-disc change), all at watch level, no emergency.
TYPICAL_DAY = "2026-10-31 12:00:00"
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
    e = HealthEngine.load(demo_dir=DEMO_DIR)
    e.comm_delay_s = float(demo()[0]["mission"].get("earth_comm_delay_s", e.comm_delay_s))
    return e


@lru_cache
def demo():
    meta = json.loads((DEMO_DIR / "crew.json").read_text())
    tel = pd.read_csv(DEMO_DIR / "telemetry.csv", parse_dates=["timestamp"])
    daily = pd.read_csv(DEMO_DIR / "daily.csv")
    cases = json.loads((DEMO_DIR / "planted_cases.json").read_text()) if (DEMO_DIR / "planted_cases.json").exists() else []
    sources = json.loads((DEMO_DIR / "sources.json").read_text()) if (DEMO_DIR / "sources.json").exists() else {}
    return meta, tel, daily, cases, sources


@lru_cache
def demo_eye_exams() -> list[dict]:
    path = DEMO_DIR / "eye_exams.json"
    exams = json.loads(path.read_text()) if path.exists() else []
    return [e | {"png": (DEMO_DIR / "eye_exams" / e["image"]).read_bytes(), "uploaded": False} for e in exams]


def eye_exams() -> list[dict]:
    """Demo photos plus the photos the astronaut uploaded."""
    mine = [e | {"png": (USER.photos_dir / e["image"]).read_bytes()} for e in USER.photos() if (USER.photos_dir / e["image"]).exists()]
    return sorted(demo_eye_exams() + mine, key=lambda e: e["date"])


def entered() -> set:
    """(date, field) pairs the astronaut entered, so the app can show them as 'you entered'."""
    return _prepared_with_entries(me()["astronaut_id"])[1]


def reset_caches():
    """The cache keys include the state of the saved entries (`_stamp`), so a save or delete is picked up at once;
    a background warm-up that started before it can only fill the old key."""
    threading.Thread(target=warm_up, daemon=True).start()


def _stamp() -> tuple:
    files = (USER.answers_path, USER.photos_path)
    return tuple(f.stat().st_mtime_ns if f.exists() else 0 for f in files)


def _profile(aid: str) -> dict:
    for p in demo()[0]["crew"]:
        if p["astronaut_id"] == aid:
            return p
    raise HTTPException(404, f"Unknown astronaut_id {aid}")


@lru_cache(maxsize=16)
def _prepared_for(aid: str, stamp: tuple) -> tuple[Prepared, set]:
    profile = _profile(aid)
    _, tel, daily, _, _ = demo()
    d, h, mine = USER.apply(daily[daily["astronaut_id"] == aid], tel[tel["astronaut_id"] == aid])
    return engine().prepare(h, profile, d, eye_exams()), mine


def _prepared_with_entries(aid: str) -> tuple[Prepared, set]:
    return _prepared_for(aid, _stamp())


def _prepared(aid: str) -> Prepared:
    """Causal tables for one astronaut's whole history (with their own entries applied), computed once per state of
    the entries. Any earlier hour is read from the same tables."""
    return _prepared_with_entries(aid)[0]


@lru_cache(maxsize=16)
def _timeline_for(aid: str, stamp: tuple) -> list[dict]:
    prep = _prepared_for(aid, stamp)[0]
    return engine().timeline(None, prep=prep, end=len(prep.hourly) - 1, hours=len(prep.hourly))


def _full_timeline(aid: str) -> list[dict]:
    """Hour-by-hour status for the whole mission (about 2 s to compute). Because every table is causal, the status at
    hour i is the same whatever moment is being replayed, so any window is a slice of this."""
    return _timeline_for(aid, _stamp())


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
            "default_at": TYPICAL_DAY,
            "replay_marks": [{"id": "typical_day", "label": "A typical day", "at": TYPICAL_DAY, "show_at": TYPICAL_DAY, "astronaut_id": me()["astronaut_id"]},
                             {"id": "quiet_day", "label": "A quiet day", "at": QUIET_DAY, "show_at": QUIET_DAY, "astronaut_id": me()["astronaut_id"]}] + [
                {"id": c["id"], "label": c["title"], "at": c["start"], "astronaut_id": c["astronaut_id"],
                 "show_at": str(pd.Timestamp(c["start"]) + pd.Timedelta(hours=SHOW_AFTER_HOURS.get(c["id"], 24)))}
                for c in sorted(cases, key=lambda c: c["start"])]}


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
            "aerobic_target_min_week": config.AEROBIC_TARGET_MIN_WEEK,
            "eye_margin_watch": fundus_rules.MARGIN_WATCH, "eye_margin_act": fundus_rules.MARGIN_ACT,
            "eye_disc_growth_act": fundus_rules.DISC_GROWTH_ACT}


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


def me() -> dict:
    """The astronaut using the app: the first (and in the solo mission, only) profile in crew.json."""
    return demo()[0]["crew"][0]


@app.get("/api/me")
def who_am_i():
    """The astronaut this app belongs to, and the flight surgeon problems are sent to."""
    mission_info = demo()[0]["mission"]
    return {**me(), "flight_surgeon": {"title": "Your flight surgeon", "where": "Mission control, Earth",
                                       "one_way_delay_s": mission_info.get("earth_comm_delay_s")}}


@app.get("/api/crew/{aid}/reports")
def reports(aid: str, at: str | None = None):
    """Everything that went to the flight surgeon up to `at`, newest first: one entry per alert episode
    (a RED episode is sent at once; a YELLOW episode goes in that day's report)."""
    prep, idx = _at(aid, at)
    tl = _full_timeline(aid)[: idx + 1]
    out, prev = [], "GREEN"
    for i, point in enumerate(tl):
        level = point["status"]
        worse = LEVEL_RANK[level] > LEVEL_RANK[prev]
        if level != "GREEN" and (worse or prev == "GREEN"):
            a = engine().assess_at(prep, i)
            esc = a["escalation"]
            same_report = out and esc["status"] == "daily_report" and out[-1]["status"] == "daily_report" \
                and out[-1]["sent_at"] == esc["sent_at"]
            if same_report:                  # several watch-level episodes in one day travel in the same daily report
                out[-1]["items"] += [x for x in esc["items"] if x not in out[-1]["items"]]
                prev = level
                continue
            out.append({"started_at": point["timestamp"], "level": level, "condition_label": a["condition_label"],
                        "status": esc["status"], "sent_at": esc["sent_at"], "arrives_at": esc["arrives_at"],
                        "summary": esc["summary"], "items": esc["items"]})
        prev = level
    return out[::-1]


@app.get("/api/crew")
def crew(at: str | None = None):
    """Status card per astronaut (one in the solo mission). Kept for compatibility with v0 clients."""
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
    result = engine().assess_at(prep, idx)
    esc = result["escalation"]
    if esc["status"] == "sent":                  # the message left when this act-now episode began, not this hour
        tl, start = _full_timeline(aid), idx
        while start > 0 and tl[start - 1]["status"] == "RED":
            start -= 1
        sent = pd.Timestamp(tl[start]["timestamp"])
        esc["sent_at"] = str(sent)
        esc["arrives_at"] = str(sent + pd.Timedelta(seconds=engine().comm_delay_s))
    mine = _prepared_with_entries(aid)[1]                # values the astronaut typed are tagged as theirs
    you = {"kind": "entered", "dataset": "you entered this"}
    for name, ind in result["indicators"].items():
        col = {"sleep_hours": "sleep_minutes"}.get(name, name)
        if (ind["date"], col) in mine:
            ind["source"] = you
    answered_at = USER.answers().get(result["timestamp"][:10], {}).get("answered_at", "")
    for name, v in result["vitals"].items():
        if (result["timestamp"][:10], name) in mine and answered_at[:13] == result["timestamp"][:13]:
            v["source"] = you
    return result


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


# ---------------------------------------------------------------- personal: questions, answers, eye photos, daily brief
def _today(prep: Prepared, idx: int) -> tuple[str, int]:
    ts = prep.hourly["timestamp"].iloc[idx]
    return str(ts.date()), int(prep.hourly["mission_day"].iloc[idx])


def _eye_due(prep: Prepared, idx: int) -> bool:
    now = prep.hourly["timestamp"].iloc[idx]
    done = [pd.Timestamp(e["date"]) for e in (prep.eye_exams or []) if pd.Timestamp(e["date"]) <= now]
    return not done or (now - max(done)).days >= EYE_EXAM_EVERY_DAYS


@app.get("/api/crew/{aid}/questions")
def questions(aid: str, at: str | None = None):
    """Today's questions: routine ones and follow-ups the engine adds from what it sees. Answered ones carry the answer."""
    prep, idx = _at(aid, at)
    date, _ = _today(prep, idx)
    a = engine().assess_at(prep, idx)
    d = int(prep.day_of_hour[idx])
    answered = USER.answers().get(date, {}).get("values", {})
    out = qbank.build(a, prep.daily.iloc[d] if d >= 0 else None, answered, _eye_due(prep, idx))
    return {"date": date, **out}


class Answers(BaseModel):
    values: dict[str, float | int | None]
    at: str | None = None


@app.post("/api/crew/{aid}/answers")
def save_answers(aid: str, body: Answers):
    """Save answers to today's questions on this device. They replace the simulated values of that day (or hour, for
    vitals) and the engine re-assesses. Returns the new assessment."""
    prep, idx = _at(aid, body.at)
    ranges = qbank.validation_ranges()
    clean = {}
    for field, value in body.values.items():
        if value is None:
            continue
        if field not in ranges:
            raise HTTPException(422, f"Unknown question: {field}")
        lo, hi = ranges[field]
        if not lo <= float(value) <= hi:
            raise HTTPException(422, f"{field} must be between {lo} and {hi}")
        clean[field] = value
    date, _ = _today(prep, idx)
    USER.save_answers(date, str(prep.hourly["timestamp"].iloc[idx]), clean)
    reset_caches()
    return assessment(aid, body.at)


class EyePhoto(BaseModel):
    image_base64: str = Field(..., description="The photo file, base64-encoded (PNG or JPEG)")
    filename: str = "photo"
    at: str | None = None


@app.post("/api/crew/{aid}/eye-photo")
def upload_eye_photo(aid: str, body: EyePhoto):
    """Check a fundus photo (any image is accepted) against your baseline photo with classical image measurement,
    store it, and send it on to the flight surgeon when it changed."""
    from io import BytesIO
    from PIL import Image, UnidentifiedImageError
    from sol_ml import fundus
    try:
        raw = base64.b64decode(body.image_base64.split(",")[-1], validate=False)
        img = Image.open(BytesIO(raw)).convert("RGB")
    except (ValueError, UnidentifiedImageError):
        raise HTTPException(422, "That file is not an image. Upload a PNG or JPEG photo.")
    img.thumbnail((1024, 1024))
    buf = BytesIO()
    img.save(buf, format="PNG")
    png = buf.getvalue()
    prep, idx = _at(aid, body.at)
    date, day = _today(prep, idx)
    when = str(prep.hourly["timestamp"].iloc[idx])
    USER.save_photo(when, day, png, body.filename)
    reset_caches()
    exam = next(e for e in eye_exams_list(aid, body.at) if e["date"] == when)
    return {"exam": exam, "assessment": assessment(aid, body.at)}


@app.get("/api/crew/{aid}/eye-exams")
def eye_exams_list(aid: str, at: str | None = None):
    """Every eye photo up to `at`, oldest first, with its measurements and the comparison with the baseline photo."""
    prep, idx = _at(aid, at)
    now = prep.hourly["timestamp"].iloc[idx]
    return [{k: v for k, v in e.items() if k != "png"} | {"url": f"/api/eye-photos/{e['image']}",
                                                         "source": {"kind": "simulated", "calibrated_on": "synthetic retina image"}
                                                         if not e.get("uploaded") else {"kind": "entered", "dataset": "your photo"}}
            for e in (prep.eye_exams or []) if pd.Timestamp(e["date"]) <= now]


@app.get("/api/eye-photos/{name}")
def eye_photo_file(name: str):
    for folder in (DEMO_DIR / "eye_exams", USER.photos_dir):
        path = (folder / name).resolve()
        if path.parent == folder.resolve() and path.exists():
            return FileResponse(path, media_type="image/png")
    raise HTTPException(404, "No such photo")


@app.get("/api/crew/{aid}/daily-brief")
def brief(aid: str, at: str | None = None):
    """Your day in a few lines, with tips. Written by rules for now, in the shape an AI model will use later."""
    prep, idx = _at(aid, at)
    a = assessment(aid, at)
    q = questions(aid, at)
    d = int(prep.day_of_hour[idx])
    return daily_brief.build(_profile(aid)["name"], a, prep.daily, max(d, 0), reports(aid, at), q["total"] - q["answered"])


@app.delete("/api/me/entries")
def clear_entries():
    """Forget every answer and photo entered on this device (the demo data stays)."""
    USER.clear()
    reset_caches()
    return {"cleared": True}


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
