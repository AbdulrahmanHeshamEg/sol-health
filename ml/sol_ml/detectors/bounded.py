"""Bounded CUSUM for live use.

The plain CUSUM chosen in notebook 02 has two problems once it runs day after day in the engine:
one extreme day (z = 7 after a quiet fortnight) lifts the sum far over the limit, and the alert then stays on for
weeks while the sum drains at k per day. Two standard guards fix that without changing when a real drift is first caught:
  z_clip  each day's z is limited to +/- z_clip before it is added (one wild day cannot carry the alarm alone)
  cap     the sum never exceeds `cap`, so it returns below the limit within (cap - h) / k days once the signal is normal again
"""
from __future__ import annotations

import numpy as np

from .baseline import zscores
from .body import DRIFT_COLS, _tag


def bounded_cusum(z: np.ndarray, k: float = 1.0, cap: float | None = None, z_clip: float | None = None) -> np.ndarray:
    """One-sided CUSUM with clipped increments and a ceiling. A missing day leaves the sum unchanged."""
    z = np.asarray(z, float)
    if z_clip is not None:
        z = np.clip(z, -z_clip, z_clip)
    s, out = np.zeros(z.shape[1:]), np.empty_like(z)
    for t in range(len(z)):
        s = np.where(np.isnan(z[t]), s, np.maximum(0.0, s + z[t] - k))
        if cap is not None:
            s = np.minimum(s, cap)
        out[t] = s
    return out


def bounded_cusum_detector(window: int = 28, k: float = 1.0, h: float = 4.0, cap: float | None = None,
                           z_clip: float | None = None, cols=DRIFT_COLS):
    """Body detector (same interface as detectors.body): alert while any bounded sum is above h."""
    cols = list(cols)

    def detect(person, X, start=None):
        return (bounded_cusum(zscores(X, window)[:, cols], k, cap, z_clip) > h).any(axis=1)
    return _tag(detect, "bounded_cusum", window=window, k=k, h=h, cap=cap, z_clip=z_clip)
