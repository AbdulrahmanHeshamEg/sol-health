"""Multi-signal detectors on the daily z-vector: "each signal looks fine alone, the combination does not"."""
from __future__ import annotations

import warnings

import numpy as np
from sklearn.covariance import EmpiricalCovariance, MinCovDet
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor


def prepare(z: np.ndarray, min_observed: int = 3) -> tuple[np.ndarray, np.ndarray]:
    """Missing signals count as normal (z = 0). Days with fewer than `min_observed` signals are not scored."""
    z = np.asarray(z, float)
    return np.nan_to_num(z, nan=0.0), (~np.isnan(z)).sum(axis=1) >= min_observed


def worse_only(flags: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Keep a flag only when the day is, on average, on the unhealthy side."""
    return flags & (np.nan_to_num(z, nan=0.0).mean(axis=1) > 0)


class IsoForest:
    """Isolation Forest; a day is flagged when it is more isolated than `contamination` of the training days."""

    def __init__(self, contamination: float = 0.01, seed: int = 42, n_estimators: int = 100):
        self.contamination, self.seed, self.n_estimators = contamination, seed, n_estimators

    def fit(self, Z):
        self.model = IsolationForest(n_estimators=self.n_estimators, random_state=self.seed).fit(Z)
        self.threshold = np.quantile(self.model.score_samples(Z), self.contamination)
        return self

    def flags(self, Z):
        return self.model.score_samples(Z) < self.threshold


class Mahalanobis:
    """Robust Mahalanobis distance (MinCovDet); flagged when d^2 exceeds the `quantile` of the training distances.
    (Empirical limit: rolling z-scores have heavier tails than a normal, so a chi-square limit fires far too often.)"""

    def __init__(self, quantile: float = 0.999, seed: int = 42):
        self.quantile, self.seed = quantile, seed

    def fit(self, Z):
        Z = np.asarray(Z, float)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                self.model = MinCovDet(random_state=self.seed).fit(Z)
                if not np.all(np.isfinite(self.model.mahalanobis(Z[:1]))):
                    raise ValueError("singular covariance")
            except Exception:              # degenerate data (e.g. constant self-reports): jittered plain covariance
                jitter = 1e-3 * np.random.default_rng(self.seed).normal(size=Z.shape)
                self.model = EmpiricalCovariance().fit(Z + jitter)
        self.limit = np.quantile(self.model.mahalanobis(Z), self.quantile)
        return self

    def flags(self, Z):
        return self.model.mahalanobis(Z) > self.limit


class LOF:
    """Local Outlier Factor in novelty mode; threshold at the `contamination` quantile of the training scores."""

    def __init__(self, contamination: float = 0.01, n_neighbors: int = 20):
        self.contamination, self.n_neighbors = contamination, n_neighbors

    def fit(self, Z):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.model = LocalOutlierFactor(n_neighbors=min(self.n_neighbors, len(Z) - 1), novelty=True).fit(Z)
        self.threshold = np.quantile(self.model.negative_outlier_factor_, self.contamination)
        return self

    def flags(self, Z):
        return self.model.score_samples(Z) < self.threshold


def rolling_flags(z: np.ndarray, make_model, min_history: int = 30, refit_every: int = 7,
                  start: int | None = None, stop: int | None = None, min_observed: int = 3) -> np.ndarray:
    """Per-person model refitted every `refit_every` days on all EARLIER scored days.
    `start`/`stop` restrict the work to a window (used when evaluating planted changes)."""
    filled, ok = prepare(z, min_observed)
    n = len(filled)
    flags = np.zeros(n, bool)
    first = min_history if start is None else start
    for b in range(first, n if stop is None else min(stop, n), refit_every):
        hist = filled[:b][ok[:b]]
        if len(hist) < min_history:
            continue
        end = min(b + refit_every, n)
        flags[b:end] = make_model().fit(hist).flags(filled[b:end]) & ok[b:end]
    return flags
