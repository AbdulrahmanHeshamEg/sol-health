"""Shared notebook setup: paths, seed, figure saving. Import with `from sol_ml.nbutil import *`."""
from __future__ import annotations

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

__all__ = ["SEED", "ROOT", "RAW", "PROCESSED", "FIGURES", "MODELS", "setup", "savefig"]


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
