"""Feature engineering shared by training and inference.

Key idea: astronauts differ a lot from each other, so the models look at each person's
deviation from their OWN baseline (first BASELINE_DAYS of the mission, resting hours),
plus short rolling context (sleep, fluids, CO2) rather than raw values alone.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import VITAL_SIGNALS, BASELINE_DAYS

ROLL_H = 6


def compute_baseline(df: pd.DataFrame) -> dict:
    """Median of each vital over awake, resting hours of the first BASELINE_DAYS days."""
    first = df[df["mission_day"] <= BASELINE_DAYS]
    if len(first) < 24:            # not enough mission history: use whatever is provided
        first = df
    rest = first[(first["activity_level"] < 0.35) & (first["is_asleep"] == 0)]
    if len(rest) < 6:
        rest = first
    return {v: float(rest[v].median()) for v in VITAL_SIGNALS}


def build_features(df: pd.DataFrame, baseline: dict | None = None) -> pd.DataFrame:
    """df: hourly rows for ONE astronaut, sorted by time. Returns a feature frame (same index)."""
    df = df.sort_values("timestamp") if "timestamp" in df else df
    if baseline is None:
        baseline = compute_baseline(df)
    f = pd.DataFrame(index=df.index)
    f["activity_level"] = df["activity_level"]
    f["is_asleep"] = df["is_asleep"]
    for v in VITAL_SIGNALS:
        f[v] = df[v]
        f[f"d_{v}"] = df[v] - baseline[v]
        f[f"r{ROLL_H}_d_{v}"] = f[f"d_{v}"].rolling(ROLL_H, min_periods=1).mean()
    # heart rate above what the current activity explains
    f["hr_excess"] = f["d_heart_rate"] - 70 * df["activity_level"]
    f["r6_hr_excess"] = f["hr_excess"].rolling(ROLL_H, min_periods=1).mean()
    f["sleep_last_24h"] = df["is_asleep"].rolling(24, min_periods=1).sum()
    f["fluid_last_6h"] = df["fluid_intake_ml"].rolling(6, min_periods=1).sum()
    f["fluid_last_24h"] = df["fluid_intake_ml"].rolling(24, min_periods=1).sum()
    f["co2"] = df["cabin_co2_mmhg"]
    f["co2_mean_6h"] = df["cabin_co2_mmhg"].rolling(6, min_periods=1).mean()
    return f.replace([np.inf, -np.inf], np.nan).fillna(0.0)


# Features used by the anomaly detector: deviations only (no context that "explains" them)
def anomaly_columns(feature_cols: list[str]) -> list[str]:
    return [c for c in feature_cols if c.startswith(("d_", "r6_d_")) or c in
            ("hr_excess", "r6_hr_excess", "activity_level", "is_asleep")]
