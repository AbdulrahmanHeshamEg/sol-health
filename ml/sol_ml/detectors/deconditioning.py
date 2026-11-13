"""Deconditioning: is the same exercise costing more heartbeats week after week?

Works on exercise *sessions* (one row each: week, activity, avg_hr, duration_min, distance). Every statistic is computed
for one evaluation week from the trailing weeks only, so it can be replayed week by week.
Each `*_stat` returns (statistic, lower bound or helper); `alerts` turns a series of them into weekly alerts.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from scipy import stats

from .evaluation import count_episodes

PACED = ("Run", "Treadmill")          # activities with a distance, so heart rate can be related to speed
NAN2 = (np.nan, np.nan)


def add_week(df: pd.DataFrame, origin: pd.Timestamp | None = None) -> pd.DataFrame:
    """Add an integer `week` column: whole weeks since `origin` (default: the Monday of the first session)."""
    start = pd.to_datetime(df["start"]).dt.normalize()
    if origin is None:
        first = start.min()
        origin = first - pd.Timedelta(days=first.weekday())
    return df.assign(week=((start - origin).dt.days // 7).astype(int))


def centered_weekly(sessions: pd.DataFrame, lo: int, hi: int, min_weeks: int = 3, value: str = "avg_hr",
                    ratio: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """Weekly median of `value` per activity type inside weeks [lo, hi], centred on that type's own median
    (subtracted, or divided when ratio=True). Types seen in fewer than `min_weeks` weeks are dropped.
    This removes "runs are harder than walks" and keeps "this week was harder than usual for the same activity"."""
    win = sessions[(sessions["week"] >= lo) & (sessions["week"] <= hi)]
    weekly = win.groupby(["activity", "week"])[value].median().dropna().reset_index()
    if weekly.empty:
        return np.array([]), np.array([])
    weekly = weekly[weekly.groupby("activity")["week"].transform("nunique") >= min_weeks]
    centre = weekly.groupby("activity")[value].transform("median")
    out = weekly[value] / centre if ratio else weekly[value] - centre
    return weekly["week"].to_numpy(float), out.to_numpy(float)


def _theil_sen(weeks: np.ndarray, y: np.ndarray, min_weeks: int, alpha: float) -> tuple[float, float]:
    if len(np.unique(weeks)) < min_weeks:
        return NAN2
    slope, _, low, _ = stats.theilslopes(y, weeks, alpha=alpha)
    return float(slope), float(low)


def trend_stat(sessions: pd.DataFrame, week: int, lookback: int = 8, min_weeks: int = 4, alpha: float = 0.9):
    """A: Theil-Sen slope (bpm per week) of the type-centred weekly median HR over the last `lookback` weeks,
    with the lower end of its confidence interval."""
    weeks, hr = centered_weekly(sessions, week - lookback + 1, week)
    return _theil_sen(weeks, hr, min_weeks, alpha)


def efficiency_stat(sessions: pd.DataFrame, week: int, lookback: int = 8, min_weeks: int = 4, alpha: float = 0.9):
    """B: trend of the efficiency index HR / speed for paced activities, in percent per week (higher = less fit)."""
    paced = sessions[sessions["activity"].isin(PACED) & (sessions["distance"] > 0) & (sessions["duration_min"] > 0)]
    if paced.empty:
        return NAN2
    paced = paced.assign(ei=paced["avg_hr"] / (paced["distance"] / paced["duration_min"] * 60.0))
    weeks, ratio = centered_weekly(paced, week - lookback + 1, week, value="ei", ratio=True)
    slope, low = _theil_sen(weeks, ratio, min_weeks, alpha)
    return 100.0 * slope, 100.0 * low


def changepoint_stat(sessions: pd.DataFrame, week: int, penalty: float = 5.0, min_weeks: int = 6):
    """D: PELT change point on the weekly type-centred HR series up to `week`.
    Returns (mean shift in bpm at the most recent change point, how many weeks ago it happened); (0, 0) if none.
    The penalty is in units of the series' noise variance, so it does not depend on the person."""
    import ruptures

    weeks, hr = centered_weekly(sessions, int(sessions["week"].min()), week)
    if len(weeks) == 0:
        return NAN2
    series = pd.Series(hr).groupby(weeks).median()
    if len(series) < min_weeks:
        return NAN2
    y = series.to_numpy(float)
    noise = 1.4826 * np.median(np.abs(np.diff(y) - np.median(np.diff(y)))) / np.sqrt(2)
    cps = ruptures.Pelt(model="l2", min_size=2, jump=1).fit(y).predict(pen=penalty * max(noise, 0.25) ** 2)[:-1]
    if not cps:
        return 0.0, 0
    cp, prev = cps[-1], (cps[-2] if len(cps) > 1 else 0)
    return float(y[cp:].mean() - y[prev:cp].mean()), int(week - series.index[cp] + 1)


def mixed_slopes(all_sessions: pd.DataFrame, week: int, lookback: int = 8, min_sessions: int = 15) -> dict:
    """C: linear mixed model on everyone's sessions in the window,
    HR ~ week + log(duration) + activity type, random intercept and random week slope per person.
    Returns {person: that person's HR trend in bpm per week}; {} if the model cannot be fitted."""
    import statsmodels.formula.api as smf

    win = all_sessions[(all_sessions["week"] > week - lookback) & (all_sessions["week"] <= week)].copy()
    win = win[win["avg_hr"].notna() & (win["duration_min"] > 0)]
    common = win["activity"].value_counts()
    win["activity"] = win["activity"].where(win["activity"].map(common) >= min_sessions, "Other")
    win["week_c"] = win["week"] - (week - (lookback - 1) / 2)
    win["log_duration"] = np.log(win["duration_min"])
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fit = smf.mixedlm("avg_hr ~ week_c + log_duration + C(activity)", win, groups=win["person"],
                              re_formula="~week_c").fit(method="lbfgs", maxiter=200)
    except Exception:
        return {}
    fixed = float(fit.fe_params["week_c"])
    return {person: fixed + float(effects.get("week_c", 0.0)) for person, effects in fit.random_effects.items()}


def inject_trend(sessions: pd.DataFrame, start_week: int, bpm_per_week: float) -> pd.DataFrame:
    """Plant a gradual loss of fitness: from `start_week`, every session's HR is higher by bpm_per_week per week."""
    weeks_in = np.clip(sessions["week"].to_numpy() - start_week + 1, 0, None)
    return sessions.assign(avg_hr=sessions["avg_hr"].to_numpy(float) + bpm_per_week * weeks_in)


def alerts(stat_rows: np.ndarray, thr: float) -> np.ndarray:
    """Trend alert in a week: statistic at or above `thr` AND its lower bound above zero."""
    s = np.asarray(stat_rows, float)
    return (s[:, 0] >= thr) & (s[:, 1] > 0)


def changepoint_alerts(stat_rows: np.ndarray, thr: float, recent: int = 4) -> np.ndarray:
    """Change-point alert in a week: an upward shift of at least `thr` bpm that began within `recent` weeks."""
    s = np.asarray(stat_rows, float)
    return (s[:, 0] >= thr) & (s[:, 1] >= 1) & (s[:, 1] <= recent)


def false_alarm_rate(weekly_alerts: list[np.ndarray], masks: list[np.ndarray]) -> float:
    """Alert episodes per person-month for WEEKLY alert series (one evaluated week = 7 of 30 days)."""
    episodes = sum(count_episodes(a & m) for a, m in zip(weekly_alerts, masks))
    return episodes / (sum(int(m.sum()) for m in masks) * 7 / 30)
