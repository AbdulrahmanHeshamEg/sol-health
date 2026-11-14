"""Eye photo check, urine and stool rules, questions, saved answers and the daily brief (light coverage)."""
import base64
import io

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from api.main import USER, app
from sol_ml import fundus
from sol_ml.engine import HealthEngine
from sol_ml.config import DEMO_DIR
from sol_ml.sim import fundus_image

client = TestClient(app)
ME, QUIET = "UH-01", "2026-09-19T12:00:00"


@pytest.fixture(autouse=True)
def no_user_entries():
    USER.clear()
    yield
    client.delete("/api/me/entries")


def test_fundus_check_flags_a_swollen_disc_and_passes_a_normal_one():
    base = fundus.measure(fundus_image.render(seed=11))
    assert fundus.compare(fundus.measure(fundus_image.render(seed=12)), base)["level"] == "GREEN"
    assert fundus.compare(fundus.measure(fundus_image.render(seed=16, swelling=0.6)), base)["level"] == "RED"


def test_fundus_check_reads_any_image_and_asks_for_a_retake():
    buf = io.BytesIO()
    Image.new("RGB", (300, 200), (30, 120, 220)).save(buf, "PNG")
    m = fundus.measure(buf.getvalue())
    assert not m["usable"] and fundus.compare(m, None)["kind"] == "retake"


def test_urine_and_stool_rules():
    e = HealthEngine.load(demo_dir=DEMO_DIR)
    days = pd.DataFrame({"urine_sg": [1.015, 1.034], "urine_blood": [0, 2], "urine_leukocytes": [0, 2], "urine_nitrite": [0, 1],
                         "urine_protein": [0, 0], "urine_glucose": [0, 0], "urine_ketones": [0, 0], "flank_pain": [0, 1],
                         "stool_bristol": [4, 7], "stool_count": [1, 4], "stool_blood": [0, 1]})
    assert e._urine_stool_alerts(days, 0) == []
    got = {a["condition"]: a["level"] for a in e._urine_stool_alerts(days, 1)}
    assert got == {"dehydration": "YELLOW", "kidney_stone_risk": "RED", "urinary_infection": "YELLOW", "diarrhea": "YELLOW", "stool_blood": "YELLOW"}


def test_demo_eye_case_and_body_systems():
    a = client.get(f"/api/crew/{ME}/assessment", params={"at": "2026-10-29T12:00:00"}).json()
    assert any(x["kind"] == "eye_exam" and x["level"] == "YELLOW" for x in a["alerts"])
    assert {"eyes", "kidneys", "gut"} <= {s["id"] for s in a["body_systems"]}
    exams = client.get(f"/api/crew/{ME}/eye-exams").json()
    assert [e["result"]["level"] for e in exams] == ["GREEN", "GREEN", "YELLOW"]
    assert client.get(exams[0]["url"]).status_code == 200


def test_questions_answers_and_follow_up():
    q = client.get(f"/api/crew/{ME}/questions", params={"at": QUIET}).json()
    assert q["total"] >= 10 and q["answered"] == 0 and all(x["why"] for g in q["groups"] for x in g["questions"])
    a = client.post(f"/api/crew/{ME}/answers", json={"at": QUIET, "values": {"urine_blood": 2, "mood": 3}}).json()
    assert a["status"] == "YELLOW" and a["indicators"]["mood"]["source"]["kind"] == "entered"
    follow = client.get(f"/api/crew/{ME}/questions", params={"at": QUIET}).json()["groups"][0]["questions"]
    assert "flank_pain" in {x["field"] for x in follow}
    a = client.post(f"/api/crew/{ME}/answers", json={"at": QUIET, "values": {"flank_pain": 1}}).json()
    assert a["status"] == "RED" and a["escalation"]["status"] == "sent"
    assert client.post(f"/api/crew/{ME}/answers", json={"at": QUIET, "values": {"mood": 9}}).status_code == 422
    client.delete("/api/me/entries")
    assert client.get(f"/api/crew/{ME}/assessment", params={"at": QUIET}).json()["status"] == "GREEN"


def test_eye_photo_upload_any_image():
    swollen = base64.b64encode(fundus_image.render(seed=40, swelling=0.6)).decode()
    out = client.post(f"/api/crew/{ME}/eye-photo", json={"at": QUIET, "image_base64": swollen, "filename": "eye.png"}).json()
    assert out["exam"]["result"]["level"] == "RED" and out["assessment"]["status"] == "RED"
    assert client.post(f"/api/crew/{ME}/eye-photo", json={"at": QUIET, "image_base64": "bm90IGFuIGltYWdl"}).status_code == 422


def test_daily_brief_has_the_ai_ready_shape():
    b = client.get(f"/api/crew/{ME}/daily-brief").json()
    assert {"greeting", "headline", "paragraphs", "changes", "tips", "ask_next", "generated_by"} <= set(b)
    assert b["generated_by"]["kind"] == "rules" and b["tips"]
