"""Shared notebook setup: paths, seed, figure saving. Import with `from sol_ml.nbutil import *`."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

SEED = 42
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "reports" / "figures"
MODELS = ROOT / "models"

__all__ = ["SEED", "ROOT", "RAW", "PROCESSED", "FIGURES", "MODELS", "setup", "savefig", "cached"]


def setup() -> np.random.Generator:
    """Seed everything, set the plot style, make the output folders. Returns a seeded Generator."""
    np.random.seed(SEED)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="notebook")
    matplotlib.rcParams.update({"figure.dpi": 110, "savefig.dpi": 150, "figure.autolayout": True})
    return np.random.default_rng(SEED)


def savefig(name: str, fig=None) -> Path:
    """Save the current figure to reports/figures/<name>.png (name starts with the notebook number)."""
    path = FIGURES / f"{name}.png"
    (fig or plt.gcf()).savefig(path, bbox_inches="tight")
    return path


def cached(name: str, key, compute):
    """Reuse a results table from data/processed/cache/ when neither `key` (any JSON-able object, e.g. the list of
    specs) nor the sol_ml library code has changed; otherwise call compute() and store its DataFrame."""
    import pandas as pd
    code = b"".join(p.read_bytes() for p in sorted((ROOT / "ml" / "sol_ml").rglob("*.py")) if p.name != "nbutil.py")
    digest = hashlib.md5(code + json.dumps(key, sort_keys=True, default=str).encode()).hexdigest()[:12]
    path = PROCESSED / "cache" / f"{name}_{digest}.parquet"
    if path.exists():
        return pd.read_parquet(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    for old in path.parent.glob(f"{name}_*.parquet"):
        old.unlink()
    df = compute()
    df.to_parquet(path, index=False)
    return df
