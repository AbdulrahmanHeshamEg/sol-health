"""Run from ml/:  python -m pytest -q"""
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
V0_KEYS = {"astronaut_id", "timestamp", "mission_day", "status", "health_score", "condition", "condition_label", "probabilities",
           "anomaly_score", "alerts", "drivers", "vitals", "context", "actions", "daily_plan", "disclaimer"}
V0_CONTEXT = {"activity_level", "is_asleep", "cabin_co2_mmhg", "sleep_last_24h", "fluid_last_24h", "ared_minutes_7d", "aerobic_minutes_7d"}
VITALS = {"heart_rate", "hrv_rmssd", "spo2", "resp_rate", "systolic_bp", "diastolic_bp", "core_temp", "pvt_reaction_ms"}


@pytest.fixture(scope="module")
def data():
    crew = json.loads((DEMO_DIR / "crew.json").read_text())
    tel = pd.read_csv(DEMO_DIR / "telemetry.csv", parse_dates=["timestamp"])
    daily = pd.read_csv(DEMO_DIR / "daily.csv")
    return crew, tel, daily


@pytest.fixture(scope="module")
def engine():
    return HealthEngine.load(demo_dir=DEMO_DIR)


def person(data, aid):
    crew, tel, daily = data
    profile = next(p for p in crew["crew"] if p["astronaut_id"] == aid)
    return tel[tel.astronaut_id == aid], profile, daily[daily.astronaut_id == aid]


def at_day(engine, data, aid, day, hour=12):
    h, p, d = person(data, aid)
    prep = engine.prepare(h, p, d)
    return engine.assess_at(prep, (day - 1) * 24 + hour)


# ---------------------------------------------------------------- response shape (docs/API.md must stay valid)
def test_assessment_keeps_the_v0_response_shape(engine, data):
    a = engine.assess(*person(data, "UH-01"))
    assert V0_KEYS <= set(a)
    assert set(a["vitals"]) == VITALS and {"value", "baseline", "delta", "unit"} <= set(a["vitals"]["spo2"])
    assert V0_CONTEXT <= set(a["context"])
    assert set(a["probabilities"]) == set(ENGINE_CONDITIONS) and abs(sum(a["probabilities"].values()) - 1) < 1e-3
    assert 0 <= a["health_score"] <= 100 and 0 <= a["anomaly_score"] <= 1
    for alert in a["alerts"]:
        assert {"source", "level", "condition", "message"} <= set(alert) and alert["source"] in ("rule", "model")
    for act in a["actions"]:
        assert set(act) == {"who", "action", "condition", "level", "priority"}


def test_every_alert_has_a_one_sentence_reason_and_a_hazard(engine, data):
    seen = 0
    for aid in ("UH-01", "UH-02", "UH-03"):
        for day in (31, 50, 66, 75):
            for alert in at_day(engine, data, aid, day)["alerts"]:
                seen += 1
                assert alert["reason"].endswith(".") and len(alert["reason"]) > 30
                assert alert["hazard"]
    assert seen >= 5


def test_every_value_is_tagged_with_its_source(engine, data):
    a = engine.assess(*person(data, "UH-02"))
    assert all(v["source"]["kind"] in ("real", "simulated") for v in a["vitals"].values())
    assert all(v["source"]["kind"] in ("real", "simulated") for v in a["indicators"].values())
    assert a["indicators"]["resting_hr"]["source"] == {"kind": "simulated", "calibrated_on": "PMData"}
    assert {"blood_glucose_mg_dl", "mood", "sleep_hours"} <= set(a["indicators"])       # the challenge's missing indicators


# ---------------------------------------------------------------- the four planted cases
def test_solar_storm_sends_the_whole_crew_to_the_shelter_now(engine, data):
    for aid in ("UH-01", "UH-02", "UH-03", "UH-04"):
        a = engine.assess(*person(data, aid))
        spe = [x for x in a["alerts"] if x["kind"] == "spe"]
        assert a["status"] == "RED" and spe and spe[0]["message"] == "SPE in progress: whole crew to the storm shelter"
        assert a["actions"][0]["action"].startswith("SPE in progress")


def test_storm_alarm_is_raised_in_the_first_hour_and_not_the_day_before(engine, data):
    h, p, d = person(data, "UH-04")
    prep = engine.prepare(h, p, d)
    onset = 74 * 24 + 5
    assert engine._spe(prep, onset)["level"] == "RED"
    assert all(engine._spe(prep, i)["level"] == "GREEN" for i in range(onset - 48, onset))


def test_slow_drift_is_caught_by_the_cusum_within_a_week(engine, data):
    h, p, d = person(data, "UH-02")
    prep = engine.prepare(h, p, d)
    drift_days = np.flatnonzero(prep.body["drift"].to_numpy()) + 1
    first = drift_days[drift_days >= 44].min()                    # the case starts on mission day 44
    assert first - 44 <= 7
    a = at_day(engine, data, "UH-02", int(first))
    alert = next(x for x in a["alerts"] if x["kind"] == "drift")
    assert alert["level"] == "YELLOW" and "normal for" in alert["reason"]


def test_cabin_case_is_labelled_likely_environmental_with_ventilation_first(engine, data):
    a = at_day(engine, data, "UH-01", 32)
    gate = next(x for x in a["alerts"] if x["kind"] == "environmental_gate")
    assert "headache" in gate["reason"] and "likely environmental" in gate["reason"]
    assert next(x for x in a["actions"] if x["condition"] == "co2_exposure")["action"].startswith("Increase ventilation first")
    crewmate = at_day(engine, data, "UH-04", 32)                  # same cabin, no symptoms: no gate alert
    assert not [x for x in crewmate["alerts"] if x["kind"] == "environmental_gate"]
    assert crewmate["context"]["cabin_co2_high"] is True


def test_odd_combination_week_raises_an_alert(engine, data):
    kinds = {x["kind"] for day in range(62, 70) for x in at_day(engine, data, "UH-03", day)["alerts"]}
    assert kinds & {"combination", "mood"}


# ---------------------------------------------------------------- rules
def test_rules_override_models(engine, data):
    h, p, d = person(data, "UH-04")
    h = h[h.mission_day <= 60].copy()
    h.loc[h.index[-1], "spo2"] = 86.0
    a = engine.assess(h, p, d[d.mission_day <= 60])
    assert a["status"] == "RED"
    assert any(x["source"] == "rule" and x["signal"] == "spo2" for x in a["alerts"])
    assert a["actions"] and a["actions"][0]["level"] == "RED"


def test_low_fasting_glucose_is_flagged(engine, data):
    h, p, d = person(data, "UH-04")
    h, d = h[h.mission_day <= 60], d[d.mission_day <= 60].copy()
    d.loc[d.index[-1], "blood_glucose_mg_dl"] = 62.0
    a = engine.assess(h, p, d)
    assert a["condition"] == "low_blood_sugar" and a["status"] == "YELLOW"
    assert next(s for s in a["body_systems"] if s["id"] == "blood")["status"] == "YELLOW"


def test_body_systems_cover_the_six_parts_of_the_figure(engine, data):
    a = engine.assess(*person(data, "UH-01"))
    assert [s["id"] for s in a["body_systems"]] == ["heart", "lungs", "brain", "bones_muscles", "blood", "immune"]
    assert next(s for s in a["body_systems"] if s["id"] == "immune")["status"] == "RED"      # the storm
    assert all(s["function"] and s["summary"] for s in a["body_systems"])


def test_works_without_a_daily_table(engine, data):
    h, p, _ = person(data, "UH-04")
    a = engine.assess(h[h.mission_day <= 60].tail(48), p)
    assert a["status"] in ("GREEN", "YELLOW", "RED") and a["indicators"] == {}


# ---------------------------------------------------------------- API
def test_api_endpoints():
    assert client.get("/api/health").json() == {"ok": True}
    cards = client.get("/api/crew").json()
    assert len(cards) == 4 and cards[0]["status"] == "RED" and cards[0]["top_reason"]
    aid = "UH-02"
    assert client.get(f"/api/crew/{aid}/assessment").json()["condition"] == "radiation_event"
    assert len(client.get(f"/api/crew/{aid}/vitals?hours=48").json()) == 48
    tl = client.get(f"/api/crew/{aid}/timeline?hours=24").json()
    assert len(tl) == 24 and set(tl[0]) >= {"timestamp", "condition", "p_abnormal", "anomaly_score"}
    fc = client.get(f"/api/crew/{aid}/forecast?horizon_days=90").json()
    assert fc["hip_bmd"]["projected_loss_if_ared_target_met_pct"] <= fc["hip_bmd"]["projected_loss_pct"]["median"]
    rad = client.get(f"/api/crew/{aid}/radiation").json()
    assert 0 < rad["career_used_pct"] < 100 and rad["spe_in_progress"] and rad["spe_level"] == "RED"
    assert rad["source"]["kind"] == "real"
    assert client.get("/api/crew/NOPE/assessment").status_code == 404
    assert client.get(f"/api/crew/{aid}/assessment", params={"at": "2026-08-31T05:00:00"}).status_code == 422


def test_api_replay_shows_an_earlier_state():
    early = client.get("/api/crew/UH-04/assessment", params={"at": "2026-10-20T12:00:00"}).json()
    assert early["timestamp"] == "2026-10-20 12:00:00" and early["status"] == "GREEN"
    quiet = client.get("/api/crew/UH-04/radiation", params={"at": "2026-10-20T12:00:00"}).json()
    assert not quiet["spe_in_progress"]


def test_api_new_endpoints_for_the_challenge_extras():
    cards = client.get("/api/indicators").json()
    assert {"blood_glucose", "mood", "sleep", "radiation"} <= {c["id"] for c in cards}
    assert all(c["why"] and c["hazard_effect"] and c["escalate"] and c["prevention"] and c["measured_in_space"] for c in cards)
    daily = client.get("/api/crew/UH-02/daily?days=14").json()
    assert len(daily) == 14 and {"resting_hr", "sleep_hours", "mood", "blood_glucose_mg_dl", "flag_drift"} <= set(daily[0])
    rem = client.get("/api/crew/UH-02/reminders").json()
    assert rem["checkin_streak_days"] >= 1 and any(i["status"] == "due" for i in rem["items"])
    cases = client.get("/api/demo/cases").json()
    assert [c["id"] for c in cases] == ["cabin_co2", "slow_drift", "solar_storm", "odd_combination"]
    meta = client.get("/api/meta").json()
    assert len(meta["citations"]) == 3 and meta["sources"]["radiation_ugy_per_day"]["kind"] == "real"
    assert meta["limits"]["cabin_co2_1h_mmhg"] == 3.0 and meta["limits"]["radiation_ratio_shelter"] == 2.0
    assert len(client.get("/api/mission").json()["replay_marks"]) == 5


def test_checkin_form_changes_the_assessment():
    at = "2026-10-20T12:00:00"
    r = client.post("/api/assess", json={"astronaut_id": "UH-04", "at": at, "checkin": {"core_temp": 39.2, "blood_glucose_mg_dl": 60}})
    assert r.status_code == 200
    a = r.json()
    assert a["status"] == "RED" and {x["condition"] for x in a["alerts"]} >= {"fever_infection", "low_blood_sugar"}
    assert a["checkin_applied"] == {"core_temp": 39.2, "blood_glucose_mg_dl": 60.0}
    again = client.get("/api/crew/UH-04/assessment", params={"at": at}).json()
    assert again["status"] == "GREEN"                              # nothing was stored
    assert client.post("/api/assess", json={"astronaut_id": "UH-04", "checkin": {"mood": 9}}).status_code == 422


def test_custom_readings_still_work(data):
    _, tel, _ = data
    rows = tel[(tel.astronaut_id == "UH-01") & (tel.mission_day <= 60)].tail(24)
    rows = rows.drop(columns=["astronaut_id", "hour", "radiation_ugy_per_day"]).copy()
    rows["timestamp"] = rows["timestamp"].astype(str)
    r = client.post("/api/assess", json={"readings": rows.to_dict(orient="records")})
    assert r.status_code == 200 and r.json()["status"] in ("GREEN", "YELLOW", "RED")


# ---------------------------------------------------------------- the v0 baseline still runs on its own demo
def test_v0_baseline_engine_still_reproduces_its_demo():
    crew = json.loads((DEMO_V0_DIR / "crew.json").read_text())
    tel = pd.read_csv(DEMO_V0_DIR / "telemetry.csv", parse_dates=["timestamp"])
    e = engine_v0.HealthEngine.load()
    p = next(c for c in crew["crew"] if c["astronaut_id"] == "UH-03")
    a = e.assess(tel[tel.astronaut_id == "UH-03"], p)
    assert (a["status"], a["condition"]) == ("RED", "co2_exposure") and set(a["probabilities"]) == set(CONDITIONS)
