"""NASA OSDR Environmental Data App (EDA): ISS cabin telemetry and ISS radiation for the Rodent Research missions.

    from sol_ml.data import osdr_eda
    cabin = osdr_eda.load_telemetry()        # mission, time (UTC), temperature/humidity/co2 for ISS and ground, co2_mmhg
    hourly = osdr_eda.to_hourly(cabin)
    dose = osdr_eda.load_radiation()         # mission, time, gcr, saa, total (mGy/day)

REAL data. Credit: "Data and visualizations are courtesy of the Environmental Data Application (EDA)
(https://visualization.osdr.nasa.gov/eda/)."
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

RAW = Path(__file__).resolve().parents[3] / "data" / "raw" / "osdr_eda"
CABIN_PRESSURE_MMHG = 760.0          # the ISS cabin is kept at one atmosphere
NUMERIC = ["temperature_iss", "temperature_ground", "humidity_iss", "humidity_ground", "co2_iss", "co2_ground"]


def ppm_to_mmhg(ppm, pressure_mmhg: float = CABIN_PRESSURE_MMHG):
    """CO2 partial pressure from a volume fraction in ppm: mmHg = ppm x cabin pressure / 1e6."""
    return ppm * pressure_mmhg / 1e6


def _utc_naive(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True).dt.tz_localize(None)


def load_telemetry(root: Path = RAW) -> pd.DataFrame:
    """All `<mission>_telemetry.csv` files stacked. Rows that share a timestamp are merged (mean of the values present).
    Adds `co2_mmhg`, the ISS CO2 partial pressure."""
    frames = []
    for path in sorted(Path(root).glob("*_telemetry.csv")):
        df = pd.read_csv(path)
        df["time"] = _utc_naive(df["time"])
        cols = [c for c in NUMERIC if c in df.columns]
        merged = df.groupby("time")[cols].mean().reset_index()
        merged.insert(0, "mission", path.name.replace("_telemetry.csv", ""))
        frames.append(merged)
    out = pd.concat(frames, ignore_index=True)
    out["co2_mmhg"] = ppm_to_mmhg(out["co2_iss"])
    return out


def to_hourly(cabin: pd.DataFrame) -> pd.DataFrame:
    """Hourly means per mission on a complete hourly index (hours without data stay NaN)."""
    cols = [c for c in cabin.columns if c not in ("mission", "time")]
    frames = []
    for mission, g in cabin.groupby("mission", sort=False):
        h = g.set_index("time")[cols].resample("1h").mean()
        h.index.name = "hour"
        frames.append(h.reset_index().assign(mission=mission))
    return pd.concat(frames, ignore_index=True)[["mission", "hour", *cols]]


def load_radiation(root: Path = RAW) -> pd.DataFrame:
    """All `<mission>_radiation.csv` files stacked: daily gcr, saa and total absorbed dose in mGy/day."""
    frames = []
    for path in sorted(Path(root).glob("*_radiation.csv")):
        df = pd.read_csv(path)
        df["time"] = _utc_naive(df["time"])
        df.insert(0, "mission", path.name.replace("_radiation.csv", ""))
        frames.append(df[["mission", "time", "gcr", "saa", "total"]])
    return pd.concat(frames, ignore_index=True)
