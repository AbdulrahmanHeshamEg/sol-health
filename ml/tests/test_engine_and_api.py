"""Run from ml/:  python -m pytest -q"""
import json

import pandas as pd
from fastapi.testclient import TestClient

from api.main import app
from sol_ml.config import CONDITIONS, DEMO_DIR
from sol_ml.engine import HealthEngine

client = TestClient(app)


def _demo():
    crew = json.load(open(DEMO_DIR / "crew.json"))
    tel = pd.read_csv(DEMO_DIR / "telemetry.csv", parse_dates=["timestamp"])
    return crew, tel


def test_demo_crew_scenarios():
    """The scripted demo must show the intended mix of states."""
    crew, tel = _demo()
    e = HealthEngine.load()
    got = {}
    for p in crew["crew"]:
        a = e.assess(tel[tel.astronaut_id == p["astronaut_id"]], p)
        got[p["astronaut_id"]] = (a["status"], a["condition"])
        assert 0 <= a["health_score"] <= 100
        assert abs(sum(a["probabilities"].values()) - 1) < 1e-3
        assert set(a["probabilities"]) == set(CONDITIONS)
    assert got["UH-01"] == ("GREEN", "nominal")
    assert got["UH-02"][1] == "dehydration" and got["UH-02"][0] == "YELLOW"
    assert got["UH-03"] == ("RED", "co2_exposure")
    assert got["UH-04"][1] == "fever_infection" and got["UH-04"][0] in ("YELLOW", "RED")


def test_rules_override_models():
    """A hard limit (SpO2 < 90) must produce RED even if the model says nominal."""
    crew, tel = _demo()
    p = crew["crew"][0]
    h = tel[tel.astronaut_id == p["astronaut_id"]].copy()
    h.loc[h.index[-1], "spo2"] = 86.0
    a = HealthEngine.load().assess(h, p)
    assert a["status"] == "RED"
    assert any(x["source"] == "rule" and x["signal"] == "spo2" for x in a["alerts"])
    assert a["actions"] and a["actions"][0]["level"] == "RED"


def test_api_endpoints():
    assert client.get("/api/health").json() == {"ok": True}
    cards = client.get("/api/crew").json()
    assert len(cards) == 4 and cards[0]["status"] == "RED"          # worst first
    aid = "UH-03"
    assert client.get(f"/api/crew/{aid}/assessment").json()["condition"] == "co2_exposure"
    assert len(client.get(f"/api/crew/{aid}/vitals?hours=48").json()) == 48
    assert len(client.get(f"/api/crew/{aid}/timeline?hours=24").json()) == 24
    fc = client.get(f"/api/crew/{aid}/forecast?horizon_days=90").json()
    assert fc["hip_bmd"]["projected_loss_if_ared_target_met_pct"] <= fc["hip_bmd"]["projected_loss_pct"]["median"]
    rad = client.get(f"/api/crew/{aid}/radiation").json()
    assert 0 < rad["career_used_pct"] < 100
    # replay: earlier in the mission UH-03 was fine
    early = client.get(f"/api/crew/{aid}/assessment", params={"at": "2026-09-20T12:00:00"}).json()
    assert early["status"] in ("GREEN", "YELLOW")
    assert client.get("/api/crew/NOPE/assessment").status_code == 404


def test_custom_assess():
    _, tel = _demo()
    rows = tel[tel.astronaut_id == "UH-01"].tail(24).drop(columns=["astronaut_id", "hour", "sim_ground_truth"])
    rows["timestamp"] = rows["timestamp"].astype(str)
    r = client.post("/api/assess", json={"readings": rows.to_dict(orient="records")})
    assert r.status_code == 200 and r.json()["status"] in ("GREEN", "YELLOW", "RED")
