"""Download ISS cabin telemetry + radiation from the NASA OSDR Environmental Data App (EDA) public API
into data/raw/osdr_eda/.

    python data/fetch/fetch_osdr_eda.py                 # every Rodent Research (RR) mission
    python data/fetch/fetch_osdr_eda.py RR-1 RR-9       # only these missions

API reference: https://visualization.osdr.nasa.gov/eda/ -> "API" (base URL .../eda/api/).
This replaces the manual download in OSDR_EDA_DOWNLOAD.md; the files are the same tables.
Output per mission: RR-<n>_telemetry.csv (time, temperature/humidity/co2 for ISS and ground)
                    RR-<n>_radiation.csv (time, gcr, saa, total; daily)
Credit: "Data and visualizations are courtesy of the Environmental Data Application (EDA)
(https://visualization.osdr.nasa.gov/eda/)."
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "raw" / "osdr_eda"
BASE = "https://visualization.osdr.nasa.gov/eda/api/missions/"


def get_json(url: str, tries: int = 3):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # network hiccup: back off and retry
            print(f"  retry {i + 1}/{tries} {url}: {e}")
            time.sleep(3 * (i + 1))
    return None


def main(argv: list[str]):
    OUT.mkdir(parents=True, exist_ok=True)
    missions = argv or [m["name"] for m in get_json(BASE) if m["name"].startswith("RR-")]
    rows = []
    for name in missions:
        info = {"mission": name}
        for kind in ("telemetry", "radiation"):
            dest = OUT / f"{name}_{kind}.csv"
            if not (dest.exists() and dest.stat().st_size > 0):
                data = get_json(f"{BASE}{name}/{kind}_data/")
                if not data:
                    print(f"{name}: no {kind} data"); continue
                pd.DataFrame(data).to_csv(dest, index=False)
                time.sleep(1)
            df = pd.read_csv(dest)
            t = pd.to_datetime(df["time"])
            info[f"{kind}_rows"] = len(df)
            if kind == "telemetry":
                info["start"], info["end"] = t.min().date(), t.max().date()
                info["days"] = round((t.max() - t.min()).total_seconds() / 86400, 1)
                info["step"] = str(t.sort_values().diff().median())
        rows.append(info)
    print(pd.DataFrame(rows).sort_values("days", ascending=False).to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1:])
