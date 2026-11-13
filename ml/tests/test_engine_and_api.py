"""Run from ml/:  python -m pytest -q   (the demo is one astronaut, UH-01, carrying all four planted cases)"""
import json

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.main import app
from sol_ml.config import DEMO_DIR, DEMO_V0_DIR, ENGINE_CONDITIONS, CONDITIONS
from sol_ml.engine import HealthEngine
from sol_ml import engine_v0

client = TestClient(app)
ME = "UH-01"
QUIET = "2026-09-19T12:00:00"             # mission day 20: before every planted case
V0_KEYS = {"astronaut_id", "timestamp", "mission_day", "status", "health_score", "condition", "condition_label", "probabilities",
           "anomaly_score", "alerts", "drivers", "vitals", "context", "actions", "daily_plan", "disclaimer"}


@pytest.fixture(scope="module")
def data():
    crew = json.loads((DEMO_DIR / "crew.json").read_text())
    tel = pd.read_csv(DEMO_DIR / "telemetry.csv", parse_dates=["timestamp"])
    daily = pd.read_csv(DEMO_DIR / "daily.csv")
    return crew["crew"][0], tel, daily


@pytest.fixture(scope="module")
def engine():
    return HealthEngine.load(demo_dir=DEMO_DIR)


@pytest.fixture(scope="module")
def prep(engine, data):
    profile, tel, daily = data
    return engine.prepare(tel, profile, daily)


def at_day(engine, prep, day, hour=12):
    return engine.assess_at(prep, (day - 1) * 24 + hour)


def until_day(data, day):
    profile, tel, daily = data
    return tel[tel.mission_day <= day].copy(), profile, daily[daily.mission_day <= day].copy()


# ---------------------------------------------------------------- shape, reasons, sources
def test_one_astronaut_and_the_v0_response_shape(engine, data, prep):
    assert data[0]["astronaut_id"] == ME
    a = engine.assess_at(prep, len(prep.hourly) - 1)
    assert V0_KEYS <= set(a) and set(a["probabilities"]) == set(ENGINE_CONDITIONS)
    assert all(v["source"]["kind"] in ("real", "simulated") for v in a["vitals"].values())
    assert {"blood_glucose_mg_dl", "mood", "sleep_hours"} <= set(a["indicators"])
    assert [s["id"] for s in a["body_systems"]] == ["heart", "lungs", "brain", "bones_muscles", "blood", "immune"]


def test_actions_are_yours_or_your_flight_surgeons(engine, prep):
    whos = {x["who"] for day in (32, 50, 62, 75) for x in at_day(engine, prep, day)["actions"]}
    assert whos <= {"self", "ground"} and whos


def test_every_alert_has_a_one_sentence_reason(engine, prep):
    alerts = [x for day in (32, 50, 62, 75) for x in at_day(engine, prep, day)["alerts"]]
    assert alerts and all(x["reason"].endswith(".") and len(x["reason"]) > 30 and x["hazard"] for x in alerts)


# ---------------------------------------------------------------- the four planted cases
def test_quiet_day_is_clear(engine, prep):
    assert at_day(engine, prep, 20)["status"] == "GREEN"


def test_cabin_case_is_likely_environmental_with_ventilation_first(engine, prep):
    a = at_day(engine, prep, 32)
    gate = next(x for x in a["alerts"] if x["kind"] == "environmental_gate")
    assert "headache" in gate["reason"] and "likely environmental" in gate["reason"]
    assert next(x for x in a["actions"] if x["condition"] == "co2_exposure")["action"].startswith("Increase ventilation first")


def test_slow_drift_is_caught_within_a_week(prep):
    days = np.flatnonzero(prep.body["drift"].to_numpy()) + 1
    assert days[days >= 40].min() - 40 <= 7                       # the case starts on mission day 40


def test_odd_combination_raises_an_alert(engine, prep):
    kinds = {x["kind"] for day in range(62, 69) for x in at_day(engine, prep, day)["alerts"]}
    assert kinds & {"combination", "mood"}


def test_solar_storm_sends_you_to_the_shelter_and_notifies_the_flight_surgeon(engine, prep):
    onset = 74 * 24 + 5
    assert engine._spe(prep, onset)["level"] == "RED"
    assert all(engine._spe(prep, i)["level"] == "GREEN" for i in range(onset - 48, onset))
    a = engine.assess_at(prep, len(prep.hourly) - 1)
    assert a["actions"][0]["action"].startswith("Solar storm in progress: go to the storm shelter")
    esc = a["escalation"]
    assert esc["status"] == "sent" and pd.Timestamp(esc["arrives_at"]) - pd.Timestamp(esc["sent_at"]) == pd.Timedelta(seconds=780)


def test_watch_level_goes_in_the_daily_report(engine, prep):
    esc = at_day(engine, prep, 32)["escalation"]
    assert esc["status"] == "daily_report" and esc["sent_at"].endswith("20:00:00")
    assert at_day(engine, prep, 20)["escalation"]["status"] == "none"


# ---------------------------------------------------------------- rules
def test_rules_override_models(engine, data):
    h, p, d = until_day(data, 20)
    h.loc[h.index[-1], "spo2"] = 86.0
    a = engine.assess(h, p, d)
    assert a["status"] == "RED" and a["escalation"]["status"] == "sent"
    assert any(x["source"] == "rule" and x["signal"] == "spo2" for x in a["alerts"])


def test_low_fasting_glucose_is_flagged(engine, data):
    h, p, d = until_day(data, 20)
    d.loc[d.index[-1], "blood_glucose_mg_dl"] = 62.0
    a = engine.assess(h, p, d)
    assert a["condition"] == "low_blood_sugar" and a["status"] == "YELLOW"


# ---------------------------------------------------------------- API
def test_api_personal_endpoints():
    me = client.get("/api/me").json()
    assert me["astronaut_id"] == ME and me["flight_surgeon"]["one_way_delay_s"] == 780
    a = client.get(f"/api/crew/{ME}/assessment").json()
    assert a["status"] == "RED" and a["condition"] == "radiation_event"
    assert client.get(f"/api/crew/{ME}/assessment", params={"at": QUIET}).json()["status"] == "GREEN"
    reports = client.get(f"/api/crew/{ME}/reports").json()
    assert reports[0]["level"] == "RED" and reports[0]["status"] == "sent"
    assert {r["status"] for r in reports} <= {"sent", "daily_report"}
    assert len(client.get(f"/api/crew/{ME}/timeline?hours=24").json()) == 24
    assert client.get("/api/crew/NOPE/assessment").status_code == 404
    assert len(client.get("/api/mission").json()["replay_marks"]) == 5
    assert client.get("/api/meta").json()["limits"]["radiation_ratio_shelter"] == 2.0


def test_checkin_form_changes_the_assessment():
    r = client.post("/api/assess", json={"astronaut_id": ME, "at": QUIET, "checkin": {"core_temp": 39.2, "blood_glucose_mg_dl": 60}})
    a = r.json()
    assert r.status_code == 200 and a["status"] == "RED" and {x["condition"] for x in a["alerts"]} >= {"fever_infection", "low_blood_sugar"}
    assert client.get(f"/api/crew/{ME}/assessment", params={"at": QUIET}).json()["status"] == "GREEN"     # nothing stored
    assert client.post("/api/assess", json={"astronaut_id": ME, "checkin": {"mood": 9}}).status_code == 422


def test_custom_readings_still_work(data):
    _, tel, _ = data
    rows = tel[tel.mission_day <= 20].tail(24).drop(columns=["astronaut_id", "hour", "radiation_ugy_per_day"]).copy()
    rows["timestamp"] = rows["timestamp"].astype(str)
    r = client.post("/api/assess", json={"readings": rows.to_dict(orient="records")})
    assert r.status_code == 200 and r.json()["status"] in ("GREEN", "YELLOW", "RED")


def test_v0_baseline_engine_still_reproduces_its_demo():
    crew = json.loads((DEMO_V0_DIR / "crew.json").read_text())
    tel = pd.read_csv(DEMO_V0_DIR / "telemetry.csv", parse_dates=["timestamp"])
    p = next(c for c in crew["crew"] if c["astronaut_id"] == "UH-03")
    a = engine_v0.HealthEngine.load().assess(tel[tel.astronaut_id == "UH-03"], p)
    assert (a["status"], a["condition"]) == ("RED", "co2_exposure") and set(a["probabilities"]) == set(CONDITIONS)
