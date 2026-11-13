"""Train all Sol Health models and write them to models/.

    cd ml && python -m sol_ml.train

Outputs
  models/risk_classifier.joblib      HistGradientBoosting, 7 conditions
  models/anomaly_detector.joblib     IsolationForest on personal-baseline deviations
  models/deconditioning.joblib       GradientBoosting (median + 10/90 % quantiles) for bone & muscle
  models/metrics.json                held-out metrics (astronaut-level split)
"""
from __future__ import annotations

import json
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import (GradientBoostingRegressor, HistGradientBoostingClassifier,
                              IsolationForest)
from sklearn.metrics import (classification_report, confusion_matrix, f1_score,
                             mean_absolute_error, roc_auc_score)
from sklearn.utils.class_weight import compute_sample_weight

from .config import CONDITIONS, MODELS_DIR
from .features import build_features, anomaly_columns
from .simulate import (random_profile, random_episodes, simulate_astronaut,
                       simulate_deconditioning_cohort, write_demo)

SEED = 42
N_TRAIN, N_TEST, DAYS = 30, 8, 120
DECON_FEATURES = ["mission_month", "age", "sex_f", "ared_minutes_week", "aerobic_minutes_week",
                  "protein_g_per_kg", "vitamin_d_ng_ml"]


def make_hourly(n_astronauts: int, rng, prefix: str):
    frames = []
    for i in range(n_astronauts):
        p = random_profile(f"{prefix}-{i:03d}", rng)
        raw = simulate_astronaut(p, DAYS, rng, random_episodes(DAYS * 24, rng),
                                 radiation_msv_per_day=float(rng.uniform(0.4, 1.8)))
        feats = build_features(raw)
        feats["label"] = raw["label"].values
        feats["astronaut_id"] = p.astronaut_id
        frames.append(feats)
    return pd.concat(frames, ignore_index=True)


def train_risk_and_anomaly(rng) -> dict:
    t0 = time.time()
    train = make_hourly(N_TRAIN, rng, "TR")
    test = make_hourly(N_TEST, rng, "TE")
    feat_cols = [c for c in train.columns if c not in ("label", "astronaut_id")]

    y_tr = train["label"].map(CONDITIONS.index).values
    y_te = test["label"].map(CONDITIONS.index).values
    clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, max_leaf_nodes=31,
                                         l2_regularization=1.0, random_state=SEED)
    clf.fit(train[feat_cols], y_tr, sample_weight=compute_sample_weight("balanced", y_tr))
    pred = clf.predict(test[feat_cols])
    proba = clf.predict_proba(test[feat_cols])

    report = classification_report(y_te, pred, labels=list(range(len(CONDITIONS))),
                                   target_names=CONDITIONS, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_te, pred, labels=list(range(len(CONDITIONS))))
    # alert-level view: did we flag "something is wrong" at all?
    abnormal_true = (y_te != 0).astype(int)
    abnormal_score = 1 - proba[:, 0]

    # --- anomaly detector, trained on nominal hours only -----------------------------
    a_cols = anomaly_columns(feat_cols)
    nominal = train[train["label"] == "nominal"][a_cols]
    iso = IsolationForest(n_estimators=300, contamination="auto", random_state=SEED)
    iso.fit(nominal)
    raw_tr = -iso.score_samples(nominal)
    lo, hi = np.percentile(raw_tr, [50, 99.5])
    raw_te = -iso.score_samples(test[a_cols])
    anom_te = np.clip((raw_te - lo) / (hi - lo), 0, 1)

    joblib.dump({"model": clf, "features": feat_cols, "classes": CONDITIONS},
                MODELS_DIR / "risk_classifier.joblib")
    joblib.dump({"model": iso, "features": a_cols, "scale": [float(lo), float(hi)]},
                MODELS_DIR / "anomaly_detector.joblib")

    return {
        "risk_classifier": {
            "train_rows": int(len(train)), "test_rows": int(len(test)),
            "train_astronauts": N_TRAIN, "test_astronauts": N_TEST, "days_each": DAYS,
            "macro_f1": round(f1_score(y_te, pred, average="macro"), 4),
            "weighted_f1": round(f1_score(y_te, pred, average="weighted"), 4),
            "abnormal_vs_nominal_auroc": round(roc_auc_score(abnormal_true, abnormal_score), 4),
            "per_class": {k: {m: round(v[m], 4) for m in ("precision", "recall", "f1-score", "support")}
                          for k, v in report.items() if k in CONDITIONS},
            "confusion_matrix": {"labels": CONDITIONS, "matrix": cm.tolist()},
            "n_features": len(feat_cols),
        },
        "anomaly_detector": {
            "trained_on_nominal_rows": int(len(nominal)),
            "abnormal_vs_nominal_auroc": round(roc_auc_score(abnormal_true, anom_te), 4),
            "flag_rate_nominal_at_0.5": round(float((anom_te[abnormal_true == 0] >= 0.5).mean()), 4),
            "flag_rate_abnormal_at_0.5": round(float((anom_te[abnormal_true == 1] >= 0.5).mean()), 4),
        },
        "seconds": round(time.time() - t0, 1),
    }


def train_deconditioning(rng) -> dict:
    df = simulate_deconditioning_cohort(1500, rng)
    df["sex_f"] = (df["sex"] == "F").astype(int)
    missions = df["mission_id"].unique()
    test_ids = set(rng.choice(missions, size=len(missions) // 5, replace=False))
    tr, te = df[~df["mission_id"].isin(test_ids)], df[df["mission_id"].isin(test_ids)]
    bundle, metrics = {"features": DECON_FEATURES, "targets": {}}, {}
    for target in ("bmd_loss_pct_month", "muscle_loss_pct_month"):
        models = {}
        for name, kw in (("median", dict(loss="squared_error")),
                         ("q10", dict(loss="quantile", alpha=0.1)),
                         ("q90", dict(loss="quantile", alpha=0.9))):
            m = GradientBoostingRegressor(n_estimators=250, max_depth=3, learning_rate=0.05,
                                          random_state=SEED, **kw)
            m.fit(tr[DECON_FEATURES], tr[target])
            models[name] = m
        pred = models["median"].predict(te[DECON_FEATURES])
        lo = models["q10"].predict(te[DECON_FEATURES]); hi = models["q90"].predict(te[DECON_FEATURES])
        bundle["targets"][target] = models
        metrics[target] = {
            "mae_pct_per_month": round(mean_absolute_error(te[target], pred), 4),
            "baseline_mae_predict_mean": round(mean_absolute_error(te[target], np.full(len(te), tr[target].mean())), 4),
            "q10_q90_coverage": round(float(((te[target] >= lo) & (te[target] <= hi)).mean()), 4),
            "test_mean_rate": round(float(te[target].mean()), 4),
        }
    joblib.dump(bundle, MODELS_DIR / "deconditioning.joblib")
    metrics["train_rows"], metrics["test_rows"] = int(len(tr)), int(len(te))
    return metrics


def main():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    metrics = {"seed": SEED}
    metrics.update(train_risk_and_anomaly(rng))
    metrics["deconditioning_forecaster"] = train_deconditioning(rng)
    with open(MODELS_DIR / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    print(json.dumps({k: v for k, v in metrics.items() if k != "risk_classifier"}, indent=2))
    print("risk_classifier macro_f1:", metrics["risk_classifier"]["macro_f1"])
    write_demo()
    from .snapshots import main as write_snapshots
    write_snapshots()


if __name__ == "__main__":
    main()
