"""Cabin CO2 generators for the simulated crew, fitted to a real hourly ISS series (mmHg).

Each generator has the signature `gen(real, n, rng) -> array of n hourly values` and is SIMULATED data:
it imitates the real series, it is not a measurement. `similarity` scores how close a generated series is.
"""
from __future__ import annotations

import numpy as np
from scipy import stats

DAY = 24
FLOOR = 0.1          # mmHg; CO2 partial pressure cannot be zero or negative


def _clean(real: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    real = np.asarray(real, float)
    keep = ~np.isnan(real)
    return real[keep], (np.arange(len(real)) % DAY)[keep]


def _diurnal_fit(values: np.ndarray, hour: np.ndarray) -> tuple[float, float, float]:
    """Least-squares mean + a*sin + b*cos with a 24-hour period."""
    w = 2 * np.pi * hour / DAY
    design = np.column_stack([np.ones(len(values)), np.sin(w), np.cos(w)])
    mean, a, b = np.linalg.lstsq(design, values, rcond=None)[0]
    return float(mean), float(a), float(b)


def _cycle(n: int, a: float, b: float) -> np.ndarray:
    w = 2 * np.pi * (np.arange(n) % DAY) / DAY
    return a * np.sin(w) + b * np.cos(w)


def gaussian_diurnal(real: np.ndarray, n: int, rng: np.random.Generator) -> np.ndarray:
    """A: mean + 24-hour sinusoid + independent Gaussian noise."""
    values, hour = _clean(real)
    mean, a, b = _diurnal_fit(values, hour)
    w = 2 * np.pi * hour / DAY
    noise_sd = np.std(values - mean - a * np.sin(w) - b * np.cos(w))
    return np.maximum(mean + _cycle(n, a, b) + rng.normal(0, noise_sd, n), FLOOR)


def ar1(real: np.ndarray, n: int, rng: np.random.Generator) -> np.ndarray:
    """B: mean + 24-hour sinusoid + AR(1) noise whose memory matches the real residuals."""
    values, hour = _clean(real)
    mean, a, b = _diurnal_fit(values, hour)
    w = 2 * np.pi * hour / DAY
    resid = values - mean - a * np.sin(w) - b * np.cos(w)
    phi = float(np.clip(np.corrcoef(resid[:-1], resid[1:])[0, 1], -0.999, 0.999))
    shocks = rng.normal(0, np.std(resid) * np.sqrt(1 - phi ** 2), n)
    out = np.empty(n)
    state = rng.normal(0, np.std(resid))
    for t in range(n):
        state = phi * state + shocks[t]
        out[t] = state
    return np.maximum(mean + _cycle(n, a, b) + out, FLOOR)


def block_bootstrap(real: np.ndarray, n: int, rng: np.random.Generator, block: int = 72) -> np.ndarray:
    """C: stitch together random `block`-hour pieces of the real series. Blocks start on a 24-hour boundary,
    so the time of day stays aligned."""
    values, _ = _clean(real)
    starts = np.arange(0, len(values) - block + 1, DAY)
    pieces = [values[s: s + block] for s in rng.choice(starts, size=int(np.ceil(n / block)))]
    return np.concatenate(pieces)[:n]


GENERATORS = {"gaussian_diurnal": gaussian_diurnal, "ar1": ar1, "block_bootstrap": block_bootstrap}


def _acf(x: np.ndarray, lags: int) -> np.ndarray:
    x = x - x.mean()
    denom = float((x * x).sum())
    return np.array([float((x[:-k] * x[k:]).sum()) / denom for k in range(1, lags + 1)])


def _profile(x: np.ndarray) -> np.ndarray:
    hour = np.arange(len(x)) % DAY
    return np.array([x[hour == h].mean() for h in range(DAY)]) - x.mean()


def similarity(real: np.ndarray, generated: np.ndarray, lags: int = 48) -> dict:
    """How close a generated series is to the real one (all lower = better):
    ks = Kolmogorov-Smirnov distance of the value distributions, acf_rmse = error of the autocorrelation over
    `lags` hours, diurnal_rmse = error of the mean-by-hour profile (mmHg)."""
    real = np.asarray(real, float)
    real = real[~np.isnan(real)]
    generated = np.asarray(generated, float)
    return {"ks": float(stats.ks_2samp(real, generated).statistic),
            "acf_rmse": float(np.sqrt(np.mean((_acf(real, lags) - _acf(generated, lags)) ** 2))),
            "diurnal_rmse": float(np.sqrt(np.mean((_profile(real) - _profile(generated)) ** 2)))}
