"""Single-signal detectors on personal z-scores (badness units: positive = worse)."""
from __future__ import annotations

import numpy as np


def threshold_alerts(z: np.ndarray, thr: float, sided: str = "worse") -> np.ndarray:
    """Alert on a day when ANY signal is beyond `thr`. sided="worse" looks only at the unhealthy direction."""
    z = np.asarray(z, float)
    z = z.reshape(len(z), -1)
    hit = (np.abs(z) if sided == "both" else z) > thr          # NaN compares False
    return hit.any(axis=1)


def cusum(z: np.ndarray, k: float = 0.5) -> np.ndarray:
    """One-sided CUSUM: S_t = max(0, S_{t-1} + z_t - k). A missing day leaves S unchanged."""
    z = np.asarray(z, float)
    s, out = np.zeros(z.shape[1:]), np.empty_like(z)
    for t in range(len(z)):
        s = np.where(np.isnan(z[t]), s, np.maximum(0.0, s + z[t] - k))
        out[t] = s
    return out


def ewma(z: np.ndarray, lam: float = 0.2) -> np.ndarray:
    """EWMA: E_t = lam*z_t + (1-lam)*E_{t-1}, starting at 0. A missing day leaves E unchanged."""
    z = np.asarray(z, float)
    e, out = np.zeros(z.shape[1:]), np.empty_like(z)
    for t in range(len(z)):
        e = np.where(np.isnan(z[t]), e, lam * z[t] + (1 - lam) * e)
        out[t] = e
    return out


def ewma_limit(lam: float, L: float) -> float:
    """Asymptotic control limit for an EWMA of unit-variance z."""
    return float(L * np.sqrt(lam / (2 - lam)))
