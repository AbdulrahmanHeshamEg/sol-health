"""Body detectors as ready-to-evaluate functions: `detector(person, X, start=None) -> bool array per day`.

`X` is days x BODY_SIGNALS in badness units (see baseline.to_badness). `start` is only a hint used when a planted
change is evaluated: detectors that refit per person (`windowed = True`) then work on [start, start + 14) only.
"""
from __future__ import annotations

import numpy as np

from . import multivariate, univariate
from .baseline import BODY_SIGNALS, ORDINAL, robust_scale, zscores
from .evaluation import HORIZON, INJECTIONS, evaluate

ALL = tuple(range(len(BODY_SIGNALS)))
DRIFT_COLS = (0, 1, 2)          # resting HR, sleep, fatigue (team plan for CUSUM)


def _tag(fn, name: str, windowed: bool = False, **params):
    fn.name, fn.params, fn.windowed = name, params, windowed
    return fn


def threshold_detector(window: int = 14, thr: float = 3.0, sided: str = "worse", cols=ALL):
    """B: personal robust z beyond `thr` on any of `cols`."""
    cols = list(cols)

    def detect(person, X, start=None):
        return univariate.threshold_alerts(zscores(X, window)[:, cols], thr, sided)
    return _tag(detect, "personal_z", window=window, thr=thr, sided=sided)


def population_detector(people, thr: float = 3.0, sided: str = "worse", cols=ALL):
    """A: z against everyone else's median and robust SD (leave-one-person-out). The baseline to beat."""
    cols = list(cols)
    stats = {}
    for p in people:
        others = np.vstack([q.X for q in people if q.name != p.name])
        stats[p.name] = (np.nanmedian(others, axis=0),
                         np.array([robust_scale(others[:, j], ordinal=s in ORDINAL) for j, s in enumerate(BODY_SIGNALS)]))

    def detect(person, X, start=None):
        med, scale = stats[person.name]
        return univariate.threshold_alerts(((X - med) / scale)[:, cols], thr, sided)
    return _tag(detect, "population_z", thr=thr, sided=sided)


def cusum_detector(window: int = 28, k: float = 0.5, h: float = 5.0, cols=DRIFT_COLS):
    """C: one-sided CUSUM on the personal z of each of `cols`; alert while any sum is above h."""
    cols = list(cols)

    def detect(person, X, start=None):
        return (univariate.cusum(zscores(X, window)[:, cols], k) > h).any(axis=1)
    return _tag(detect, "cusum", window=window, k=k, h=h)


def ewma_detector(window: int = 28, lam: float = 0.2, L: float = 3.0, cols=DRIFT_COLS):
    """D: EWMA control chart on the personal z of each of `cols`."""
    cols = list(cols)
    limit = univariate.ewma_limit(lam, L)

    def detect(person, X, start=None):
        return (univariate.ewma(zscores(X, window)[:, cols], lam) > limit).any(axis=1)
    return _tag(detect, "ewma", window=window, lam=lam, L=L)


def multivariate_detector(make_model, window: int = 14, mode: str = "rolling", people=None, name: str = "multivariate",
                          min_history: int = 30, refit_every: int = 7, **params):
    """E/F/G on the daily z-vector. mode="rolling": one model per person, refitted weekly on that person's past.
    mode="pooled": one model per person trained on every OTHER person's z-vectors (needs `people`)."""
    if mode == "pooled":
        models = {}
        for p in people:
            rows = []
            for q in people:
                if q.name != p.name:
                    filled, ok = multivariate.prepare(zscores(q.X, window))
                    rows.append(filled[ok])
            models[p.name] = make_model().fit(np.vstack(rows))

        def detect(person, X, start=None):
            z = zscores(X, window)
            filled, ok = multivariate.prepare(z)
            flags = np.zeros(len(X), bool)
            lo, hi = (0, len(X)) if start is None else (start, min(start + HORIZON, len(X)))
            flags[lo:hi] = models[person.name].flags(filled[lo:hi]) & ok[lo:hi]
            return multivariate.worse_only(flags, z)
        return _tag(detect, name, mode=mode, window=window, **params)

    def detect(person, X, start=None):
        z = zscores(X, window)
        stop = None if start is None else start + HORIZON
        flags = multivariate.rolling_flags(z, make_model, min_history, refit_every, start, stop)
        return multivariate.worse_only(flags, z)
    return _tag(detect, name, windowed=True, mode=mode, window=window, **params)


def any_of(*detectors, name: str = "combination"):
    """Alert when any member alerts."""
    def detect(person, X, start=None):
        out = np.zeros(len(X), bool)
        for d in detectors:
            out |= d(person, X, start=start)
        return out
    return _tag(detect, name, windowed=any(getattr(d, "windowed", False) for d in detectors),
                members=[getattr(d, "name", "?") for d in detectors])


MODEL_KINDS = {
    "iforest": lambda rate: multivariate.IsoForest(rate, n_estimators=50),
    "mahalanobis": lambda rate: multivariate.Mahalanobis(1 - rate),
    "lof": lambda rate: multivariate.LOF(rate),
}


def build(spec: dict, people=None):
    """Detector from a plain dict, e.g. {"kind": "cusum", "window": 28, "k": 0.5, "h": 5}.
    Multivariate kinds take `rate` (share of training days flagged), `mode` and `window`.
    {"kind": "any_of", "members": [spec, ...]} combines detectors."""
    spec = dict(spec)
    kind = spec.pop("kind")
    if kind == "personal_z":
        return threshold_detector(**spec)
    if kind == "population_z":
        return population_detector(people, **spec)
    if kind == "cusum":
        return cusum_detector(**spec)
    if kind == "ewma":
        return ewma_detector(**spec)
    if kind in MODEL_KINDS:
        rate = spec.pop("rate")
        return multivariate_detector(lambda: MODEL_KINDS[kind](rate), people=people, name=kind, rate=rate, **spec)
    if kind == "any_of":
        return any_of(*[build(m, people) for m in spec["members"]])
    raise ValueError(f"unknown detector kind: {kind}")


def run_spec(spec: dict, people, sites: dict, seed: int = 42) -> dict:
    """Evaluate one spec with the shared protocol and return one flat row for a results table."""
    res = evaluate(build(spec, people), people, sites, seed)
    row = {"kind": spec["kind"], "false_alarms": res["false_alarms_per_person_month"]}
    row.update({k: (str(v) if isinstance(v, (list, tuple, dict)) else v) for k, v in spec.items() if k != "kind"})
    for name in sites:
        for key, short in (("median_delay_censored", "delay"), ("median_delay", "delay_hit"),
                           ("p90_delay", "p90"), ("miss_rate", "miss")):
            row[f"{name}_{short}"] = res[name][key]
    row["mean_delay"] = float(np.mean([res[name]["median_delay_censored"] for name in sites]))
    row["mean_miss"] = float(np.mean([res[name]["miss_rate"] for name in sites]))
    return row
