"""Shared evaluation protocol (docs/NOTEBOOKS.md): false alarms per person-month on real data and
detection delay on changes planted into real series. All arrays are days x BODY_SIGNALS in badness units."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .baseline import BODY_SIGNALS, ORDINAL, robust_scale, to_badness

HORIZON = 14          # days after the start in which a planted change must be caught
DAYS_PER_MONTH = 30
_HR, _SLEEP, _FATIGUE, _MOOD, _STRESS = range(5)
# name -> (affected columns, shift in personal robust SDs, ramp days, duration days)
INJECTIONS = {
    "drift_hr": ([_HR], [2.0], 7, HORIZON),
    "drift_multi": ([_HR, _SLEEP, _FATIGUE], [1.5, 1.5, 1.5], 7, HORIZON),
    "combo_odd": ([_MOOD, _STRESS, _SLEEP], [1.5, 1.5, 1.5], 1, 5),
    "step_sleep": ([_SLEEP], [2.0], 1, 5),
}
_ORDINAL_COLS = [j for j, s in enumerate(BODY_SIGNALS) if s in ORDINAL]


def count_episodes(alerts: np.ndarray) -> int:
    """Consecutive alert days are one episode."""
    a = np.asarray(alerts, bool).astype(int)
    return int((np.diff(np.concatenate([[0], a])) == 1).sum())


def eval_mask(injury: np.ndarray, warmup: int = 14, pad: int = 2) -> np.ndarray:
    """Days that count for false alarms: after the warm-up and not within `pad` days of an injury report."""
    mask = np.ones(len(injury), bool)
    mask[:warmup] = False
    for i in np.flatnonzero(injury):
        mask[max(0, i - pad): i + pad + 1] = False
    return mask


def false_alarm_rate(alerts: list[np.ndarray], masks: list[np.ndarray]) -> float:
    """Alert episodes per person-month (30 evaluated days), pooled over people."""
    episodes = sum(count_episodes(a & m) for a, m in zip(alerts, masks))
    return episodes / (sum(int(m.sum()) for m in masks) / DAYS_PER_MONTH)


def inject(X: np.ndarray, name: str, start: int, scales: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Plant a known change into a copy of X. Shifts are in the person's own robust SDs and always point to worse.
    Missing days stay missing. Self-reports stay whole numbers on the 1-5 scale (random rounding keeps the mean shift)."""
    cols, sds, ramp, duration = INJECTIONS[name]
    out = np.array(X, float)
    days = np.arange(start, min(start + duration, len(out)))
    profile = np.minimum((days - start + 1) / ramp, 1.0)
    for j, sd in zip(cols, sds):
        value = out[days, j] + sd * scales[j] * profile
        if j in _ORDINAL_COLS:
            low = np.floor(value)
            value = np.clip(low + (rng.random(len(days)) < (value - low)), -5, -1)
        out[days, j] = value
    return out


def delay(clean: np.ndarray, injected: np.ndarray, start: int, horizon: int = HORIZON) -> float:
    """Days from the start of the planted change to the first NEW alert (one the clean series did not have).
    NaN = missed within the horizon."""
    new = (injected & ~clean)[start: start + horizon]
    return float(np.argmax(new)) if new.any() else np.nan


def summarize(delays: np.ndarray, horizon: int = HORIZON) -> dict:
    d = np.asarray(delays, float)
    hit = d[~np.isnan(d)]
    return {"median_delay": float(np.median(hit)) if len(hit) else np.nan,
            "p90_delay": float(np.percentile(hit, 90)) if len(hit) else np.nan,
            "miss_rate": float(np.isnan(d).mean()),
            "median_delay_censored": float(np.median(np.where(np.isnan(d), horizon, d))),
            "n": int(len(d))}


@dataclass
class Person:
    name: str
    dates: pd.DatetimeIndex
    X: np.ndarray            # days x BODY_SIGNALS, badness units
    injury: np.ndarray
    mask: np.ndarray         # days that count for false alarms
    scales: np.ndarray       # whole-record robust SD per signal (sizes the planted changes)


def load_people(daily: pd.DataFrame, names: list[str], warmup: int = 14) -> list[Person]:
    people = []
    for name in names:
        g = daily[daily.person == name].sort_values("date")
        X = to_badness(g).to_numpy(float)
        injury = g["injury"].to_numpy(bool)
        scales = np.array([robust_scale(X[:, j], ordinal=s in ORDINAL) for j, s in enumerate(BODY_SIGNALS)])
        people.append(Person(name, pd.DatetimeIndex(g["date"]), X, injury, eval_mask(injury, warmup), scales))
    return people


def sample_sites(people: list[Person], name: str, n: int, rng: np.random.Generator,
                 warmup: int = 28, min_coverage: float = 0.5) -> list[tuple[int, int]]:
    """Random (person index, start day) pairs: after the warm-up, a full horizon before the end, no injury nearby,
    and the affected signals observed on at least `min_coverage` of the days the change lasts."""
    cols, _, _, duration = INJECTIONS[name]
    valid = []
    for i, p in enumerate(people):
        for s in range(warmup, len(p.X) - HORIZON):
            if not p.mask[s: s + HORIZON].all():
                continue
            seen = ~np.isnan(p.X[s: s + duration][:, cols])
            if seen.mean(axis=0).min() >= min_coverage:
                valid.append((i, s))
    picks = rng.choice(len(valid), size=n, replace=len(valid) < n)
    return [valid[k] for k in picks]


def evaluate(detector, people: list[Person], sites: dict[str, list[tuple[int, int]]], seed: int = 42) -> dict:
    """Run the full protocol for one detector. `detector(person, X, start=None)` returns a bool array per day.
    Detectors with `windowed = True` are refitted from the planted start, so their clean run uses the same grid."""
    clean = [detector(p, p.X) for p in people]
    result = {"false_alarms_per_person_month": false_alarm_rate(clean, [p.mask for p in people])}
    windowed = getattr(detector, "windowed", False)
    for name, pairs in sites.items():
        rng = np.random.default_rng(seed)
        delays = []
        for i, s in pairs:
            p = people[i]
            planted = detector(p, inject(p.X, name, s, p.scales, rng), start=s)
            base = detector(p, p.X, start=s) if windowed else clean[i]
            delays.append(delay(base, planted, s))
        result[name] = summarize(np.array(delays))
    return result
