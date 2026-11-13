"""Personal baselines: turn a raw daily signal into "how far from this person's own normal".

Everything works in *badness* units: after `to_badness`, a higher number is always worse
(higher resting HR, less sleep, worse self-report). PMSys self-reports are 1-5 with 5 = best, so they are flipped.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

BODY_SIGNALS = ["resting_hr", "sleep_minutes", "fatigue", "mood", "stress"]
BAD_SIGN = {"resting_hr": 1, "sleep_minutes": -1, "fatigue": -1, "mood": -1, "stress": -1,
            "sleep_score": -1, "readiness": -1, "soreness": -1, "sleep_quality": -1, "sleep_duration_h": -1}
ORDINAL = {"fatigue", "mood", "stress", "soreness", "sleep_quality"}
ORDINAL_FLOOR = 0.5          # half a scale point: the smallest scale a 1-5 report may have
MAD_TO_SD, MEANAD_TO_SD = 1.4826, 1.2533


def to_badness(df: pd.DataFrame, signals: list[str] = BODY_SIGNALS) -> pd.DataFrame:
    """Flip signals where higher is better, so that higher always means worse."""
    return pd.DataFrame({s: df[s] * BAD_SIGN[s] for s in signals}, index=df.index)


def robust_scale(x: np.ndarray, ordinal: bool = False) -> float:
    """Robust SD: 1.4826*MAD. If the MAD is 0 (a signal that sits on one value most days), fall back to
    1.2533 * mean absolute deviation. Ordinal 1-5 reports never get a scale below half a point."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if len(x) == 0:
        return np.nan
    dev = np.abs(x - np.median(x))
    scale = MAD_TO_SD * np.median(dev)
    if scale == 0:
        scale = MEANAD_TO_SD * dev.mean()
    return max(float(scale), ORDINAL_FLOOR) if ordinal else float(scale)


def rolling_z(x: np.ndarray, window: int = 14, min_periods: int | None = None, ordinal: bool = False) -> np.ndarray:
    """Robust z of each day against the PREVIOUS `window` days (a day is never part of its own baseline).
    NaN when the day is missing or fewer than `min_periods` baseline days have a value."""
    x = np.asarray(x, float)
    min_periods = min_periods or max(5, window // 2)
    padded = np.concatenate([np.full(window, np.nan), x])
    past = sliding_window_view(padded, window)[: len(x)]              # row t = x[t-window : t]
    count = (~np.isnan(past)).sum(axis=1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)               # all-NaN windows
        med = np.nanmedian(past, axis=1)
        dev = np.abs(past - med[:, None])
        scale = MAD_TO_SD * np.nanmedian(dev, axis=1)
        fallback = MEANAD_TO_SD * np.nanmean(dev, axis=1)
    scale = np.where(scale == 0, fallback, scale)
    if ordinal:
        scale = np.maximum(scale, ORDINAL_FLOOR)
    scale = np.where((scale > 0) & (count >= min_periods), scale, np.nan)
    return (x - med) / scale


def zscores(X: np.ndarray, window: int = 14, signals: list[str] = BODY_SIGNALS) -> np.ndarray:
    """rolling_z for every column of a days x signals badness array."""
    return np.column_stack([rolling_z(X[:, j], window, ordinal=s in ORDINAL) for j, s in enumerate(signals)])
