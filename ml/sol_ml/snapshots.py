"""Save real API responses to data/demo/api_snapshots/ for frontend mock mode.

    cd ml && python -m sol_ml.snapshots

File names: `<name>.json` for the current moment, and `at/<mark>/<name>.json` for each replay mark
(the start of every planted case plus a quiet day), so the mock mode can also replay the mission.
"""
import json
import shutil

from .config import DEMO_DIR

GLOBAL = {"mission": "/api/mission", "meta": "/api/meta", "crew": "/api/crew", "me": "/api/me", "indicators": "/api/indicators",
          "cases": "/api/demo/cases"}
PER_CREW = {"profile": "/api/crew/{id}", "assessment": "/api/crew/{id}/assessment", "vitals_72h": "/api/crew/{id}/vitals?hours=72",
            "timeline_72h": "/api/crew/{id}/timeline?hours=72", "daily_30d": "/api/crew/{id}/daily?days=30",
            "forecast": "/api/crew/{id}/forecast?horizon_days=90", "radiation": "/api/crew/{id}/radiation",
            "reminders": "/api/crew/{id}/reminders", "reports": "/api/crew/{id}/reports",
            "questions": "/api/crew/{id}/questions", "brief": "/api/crew/{id}/daily-brief", "eye_exams": "/api/crew/{id}/eye-exams", "timeline_all": "/api/crew/{id}/timeline?hours=1800",
            "daily_all": "/api/crew/{id}/daily?days=75"}
TIMED = ("mission", "crew")
TIMED_PER_CREW = ("assessment", "vitals_72h", "timeline_72h", "daily_30d", "forecast", "radiation", "reminders", "reports",
                  "questions", "brief", "eye_exams")


def main():
    from fastapi.testclient import TestClient
    from api.main import app
    client = TestClient(app)
    out = DEMO_DIR / "api_snapshots"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)

    def save(path, url, at=None):
        r = client.get(url, params={"at": at} if at else None)
        r.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(r.json(), indent=1))

    from api.main import USER
    if USER.answers() or USER.photos():
        raise SystemExit("Clear your own entries first (DELETE /api/me/entries): snapshots must show the demo data only.")
    shutil.copytree(DEMO_DIR / "eye_exams", out / "eye-photos")          # the demo eye photos, for offline mode
    crew_ids = [c["astronaut_id"] for c in client.get("/api/crew").json()]
    for name, url in GLOBAL.items():
        save(out / f"{name}.json", url)
    for cid in crew_ids:
        for name, url in PER_CREW.items():
            save(out / f"{cid}_{name}.json", url.format(id=cid))

    mission = client.get("/api/mission").json()
    marks = [{"id": m["id"], "label": m["label"], "at": m["show_at"]} for m in mission["replay_marks"]]
    n = 0
    for mark in marks:
        base = out / "at" / mark["id"]
        for name in TIMED:
            save(base / f"{name}.json", GLOBAL[name], mark["at"])
        for cid in crew_ids:
            for name in TIMED_PER_CREW:
                save(base / f"{cid}_{name}.json", PER_CREW[name].format(id=cid), mark["at"])
                n += 1
    (out / "replay_marks.json").write_text(json.dumps(marks, indent=1))
    print(f"snapshots -> {out}: {len(GLOBAL) + len(crew_ids) * len(PER_CREW)} current, {n} replay files, marks: {[m['id'] for m in marks]}")


if __name__ == "__main__":
    main()
