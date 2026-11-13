"""Radiation: cumulative dose counter and solar-particle-event (SPE) detectors on an hourly dose-rate series.

Every score for hour t uses only hours before t (trailing window), so the detectors can run live.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from .univariate import cusum as _cusum, ewma as _ewma

WEEK_HOURS = 168
METHODS = ("robust_z", "ratio", "cusum", "ewma")
QUALITY_FACTOR = 3.0          # Hassler et al. 2014: absorbed dose (Gy) -> dose equivalent (Sv) on the Mars surface
YELLOW_SHARE, RED_SHARE = 0.8, 1.0


def trailing_baseline(x: np.ndarray, window: int = WEEK_HOURS, min_periods: int | None = None):
    """Median and robust SD (1.4826*MAD) of the PREVIOUS `window` hours, ignoring gaps.
    NaN until `min_periods` earlier values exist. The scale never drops below 1 % of the median."""
    x = np.asarray(x, float)
    min_periods = min_periods or max(3, window // 4)
    past = sliding_window_view(np.concatenate([np.full(window, np.nan), x]), window)[: len(x)]
    count = (~np.isnan(past)).sum(axis=1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        med = np.nanmedian(past, axis=1)
        scale = 1.4826 * np.nanmedian(np.abs(past - med[:, None]), axis=1)
    scale = np.maximum(scale, 0.01 * np.abs(med))
    enough = count >= min_periods
    return np.where(enough, med, np.nan), np.where(enough, scale, np.nan)


def spe_score(x: np.ndarray, method: str = "robust_z", window: int = WEEK_HOURS, k: float = 1.0,
              lam: float = 0.3) -> np.ndarray:
    """Hourly SPE score. robust_z: (x - median)/robust SD. ratio: x/median.
    cusum / ewma: CUSUM (slack k) or EWMA (weight lam) of the robust z of log dose rate."""
    x = np.asarray(x, float)
    med, scale = trailing_baseline(x, window)
    if method == "robust_z":
        return (x - med) / scale
    if method == "ratio":
        return x / med
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        z_log = (np.log(x) - np.log(med)) / (scale / med)
    if method == "cusum":
        return _cusum(z_log, k)
    if method == "ewma":
        return _ewma(z_log, lam)
    raise ValueError(f"unknown method: {method}")


def deseasonalize(x: np.ndarray, local_hour: np.ndarray, n_sols: int = 7, min_sols: int = 4) -> np.ndarray:
    """Remove the daily (diurnal) cycle: divide each hour by the median of the same local hour over the previous
    `n_sols` sols and multiply by the overall trailing median, so the level and the units stay the same."""
    x = np.asarray(x, float)
    bins = np.floor(np.asarray(local_hour, float)).astype(int) % 24
    same_hour = np.full(len(x), np.nan)
    for b in range(24):
        idx = np.flatnonzero(bins == b)
        if len(idx):
            same_hour[idx] = pd.Series(x[idx]).shift(1).rolling(n_sols, min_periods=min_sols).median().to_numpy()
    overall, _ = trailing_baseline(x, int(round(n_sols * 24.66)))
    return x * overall / same_hour


def persistent(alerts: np.ndarray, hours: int = 2) -> np.ndarray:
    """Keep an alert only when it has held for `hours` consecutive hours (removes single-hour glitches)."""
    a = np.asarray(alerts, bool)
    out = a.copy()
    for lag in range(1, hours):
        out[lag:] &= a[:-lag]
        out[:lag] = False
    return out


def onset_hour(x: np.ndarray, start: int, stop: int, window: int = WEEK_HOURS, factor: float = 2.0) -> int | None:
    """Reference onset of an event: the first hour in [start, stop] above `factor` x the trailing median."""
    x = np.asarray(x, float)
    med, _ = trailing_baseline(x, window)
    hit = np.flatnonzero(x[start: stop + 1] > factor * med[start: stop + 1])
    return int(start + hit[0]) if len(hit) else None


def changepoint_score(x: np.ndarray, t: int, lookback: int = 336, penalty: float = 10.0, recent: int = 6) -> float:
    """Change-point evidence at hour t: PELT (least squares) on the log dose rate of the last `lookback` hours.
    Returns the upward jump at the latest change point in noise SDs, if it happened within `recent` hours; else 0.
    The penalty is in units of the noise variance (estimated from hour-to-hour differences)."""
    import ruptures

    seg = np.asarray(x, float)[max(0, t - lookback + 1): t + 1]
    seg = np.log(seg[~np.isnan(seg) & (seg > 0)])
    if len(seg) < 48:
        return 0.0
    diffs = np.diff(seg)
    noise = max(1.4826 * np.median(np.abs(diffs - np.median(diffs))) / np.sqrt(2), 1e-3)
    # KernelCPD with a linear kernel is the same least-squares PELT, implemented in C (about 1000x faster)
    cps = ruptures.KernelCPD(kernel="linear", min_size=2).fit(seg.reshape(-1, 1)).predict(pen=penalty * noise ** 2)[:-1]
    if not cps or len(seg) - cps[-1] > recent:
        return 0.0
    cp, prev = cps[-1], (cps[-2] if len(cps) > 1 else 0)
    return float(max(seg[cp:].mean() - seg[prev:cp].mean(), 0.0) / noise)


def count_events(alerts: np.ndarray, gap_hours: int = 24) -> int:
    """Number of separate alert events: alert hours closer than `gap_hours` belong to the same event."""
    hours = np.flatnonzero(np.asarray(alerts, bool))
    return int(len(hours) > 0) + int((np.diff(hours) > gap_hours).sum())


def cumulative_dose_msv(daily_ugy_per_day: np.ndarray, quality_factor: float = QUALITY_FACTOR) -> np.ndarray:
    """Cumulative dose equivalent in mSv from daily absorbed dose rates in uGy/day.
    A day without data is counted at the median of the previous 7 days (never as zero)."""
    d = pd.Series(np.asarray(daily_ugy_per_day, float))
    filled = d.fillna(d.rolling(7, min_periods=1).median().ffill()).fillna(0.0)
    return (filled.cumsum() * quality_factor / 1000.0).to_numpy()


def dose_status(cumulative_msv: float, budget_msv: float) -> str:
    """GREEN / YELLOW (80 % of the budget) / RED (100 %)."""
    share = cumulative_msv / budget_msv
    return "RED" if share >= RED_SHARE else "YELLOW" if share >= YELLOW_SHARE else "GREEN"
