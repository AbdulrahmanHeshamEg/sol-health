"""Save real API responses to data/demo/api_snapshots/ for frontend mock mode.

    cd ml && python -m sol_ml.snapshots
"""
import json

from .config import DEMO_DIR

CALLS = {
    "mission": "/api/mission", "meta": "/api/meta", "crew": "/api/crew",
    "UH-03_profile": "/api/crew/UH-03", "UH-03_assessment": "/api/crew/UH-03/assessment",
    "UH-01_assessment": "/api/crew/UH-01/assessment",
    "UH-03_vitals_48h": "/api/crew/UH-03/vitals?hours=48",
    "UH-03_timeline_72h": "/api/crew/UH-03/timeline?hours=72",
    "UH-03_forecast": "/api/crew/UH-03/forecast?horizon_days=90",
    "UH-03_radiation": "/api/crew/UH-03/radiation",
}


def main():
    from fastapi.testclient import TestClient
    from api.main import app
    client = TestClient(app)
    out = DEMO_DIR / "api_snapshots"
    out.mkdir(parents=True, exist_ok=True)
    for crew_id in ("UH-01", "UH-02", "UH-04"):          # full set for every astronaut
        CALLS.setdefault(f"{crew_id}_profile", f"/api/crew/{crew_id}")
        CALLS.setdefault(f"{crew_id}_assessment", f"/api/crew/{crew_id}/assessment")
        CALLS[f"{crew_id}_vitals_72h"] = f"/api/crew/{crew_id}/vitals?hours=72"
        CALLS[f"{crew_id}_timeline_72h"] = f"/api/crew/{crew_id}/timeline?hours=72"
        CALLS[f"{crew_id}_forecast"] = f"/api/crew/{crew_id}/forecast?horizon_days=90"
        CALLS[f"{crew_id}_radiation"] = f"/api/crew/{crew_id}/radiation"
    CALLS["UH-03_vitals_72h"] = "/api/crew/UH-03/vitals?hours=72"
    for name, url in CALLS.items():
        r = client.get(url)
        r.raise_for_status()
        with open(out / f"{name}.json", "w") as f:
            json.dump(r.json(), f, indent=2)
    print(f"{len(CALLS)} snapshots -> {out}")


if __name__ == "__main__":
    main()
