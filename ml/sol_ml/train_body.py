"""Fit the pooled Isolation Forest of the body model on real PMData z-vectors and save it.

    cd ml && python -m sol_ml.train_body

Reads models/engine_config.json (written by notebook 02) for the window and the flag rate, fits on the daily
z-vectors of the 14 usable PMData people, and writes models/body_iforest.joblib. The file holds the forest,
its flag threshold and the sorted training scores (used to express "how unusual" as a percentile).
"""
from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd

from .config import DATA_DIR, MODELS_DIR
from .detectors import multivariate
from .detectors.baseline import BODY_SIGNALS, zscores
from .detectors.evaluation import load_people

EXCLUDED = ("p12", "p13")


def iforest_spec(config: dict) -> dict:
    return next(m for m in config["body"]["members"] if m["kind"] == "iforest")


def main():
    config = json.loads((MODELS_DIR / "engine_config.json").read_text())
    spec = iforest_spec(config)
    daily = pd.read_parquet(DATA_DIR / "processed" / "pmdata_daily.parquet")
    people = load_people(daily, [p for p in sorted(daily.person.unique()) if p not in EXCLUDED])
    rows = []
    for p in people:
        filled, ok = multivariate.prepare(zscores(p.X, spec["window"]))
        rows.append(filled[ok])
    Z = np.vstack(rows)
    model = multivariate.IsoForest(spec["rate"], seed=42, n_estimators=50).fit(Z)
    joblib.dump({"model": model, "signals": BODY_SIGNALS, "window": spec["window"], "rate": spec["rate"],
                 "train_scores": np.sort(model.model.score_samples(Z)), "trained_on": "PMData, 14 people",
                 "train_rows": int(len(Z))}, MODELS_DIR / "body_iforest.joblib")
    print(f"body_iforest.joblib: {len(Z)} real person-days, window {spec['window']}, flag rate {spec['rate']}")


if __name__ == "__main__":
    main()
