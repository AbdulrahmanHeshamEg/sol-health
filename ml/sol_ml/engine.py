"""Inference engine: turns raw telemetry into an assessment the app can display.

    from sol_ml.engine import HealthEngine
    engine = HealthEngine.load()
    result = engine.assess(history_df, profile)        # one astronaut
    fc = engine.forecast_deconditioning(profile, history_df, horizon_days=90)
    rad = engine.radiation_status(profile, history_df, mission)

Decision logic (documented in docs/MODELS.md "How the outputs combine"):
  1. Hard clinical limits (rules) are checked first and always win.
  2. Risk classifier gives the most likely condition (probabilities smoothed over 3 h).
  3. Anomaly detector says how unusual the last hour is for this person (0..1).
  4. Level = worst of rule level and model level. Health score summarises all three.
"""
from __future__ import annotations

import joblib
import numpy as np
import pandas as pd

from .config import (MODELS_DIR, CONDITIONS, CONDITION_LABELS, HARD_LIMITS, RESTING_HR_RED,
                     RESTING_HR_YELLOW, VITAL_SIGNALS, CAREER_RADIATION_LIMIT_MSV,
                     SPE_EVENT_LIMIT_MSV, BMD_LOSS_ALERT_PCT, ARED_TARGET_MIN_WEEK, WINDOW_HOURS)
from .features import build_features, compute_baseline
from .protocols import actions_for, daily_plan
from .simulate import NOISE_SD

LEVEL_RANK = {"GREEN": 0, "YELLOW": 1, "RED": 2}
OPS = {"<": np.less, ">": np.greater, ">=": np.greater_equal, "<=": np.less_equal}
UNITS = {"heart_rate": "bpm", "hrv_rmssd": "ms", "spo2": "%", "resp_rate": "br/min",
         "systolic_bp": "mmHg", "diastolic_bp": "mmHg", "core_temp": "C", "pvt_reaction_ms": "ms"}


def _worst(*levels):
    return max(levels, key=lambda lv: LEVEL_RANK[lv])


class HealthEngine:
    def __init__(self, risk, anomaly, decon):
        self.risk, self.anomaly, self.decon = risk, anomaly, decon

    @classmethod
    def load(cls, models_dir=MODELS_DIR) -> "HealthEngine":
        return cls(joblib.load(models_dir / "risk_classifier.joblib"),
                   joblib.load(models_dir / "anomaly_detector.joblib"),
                   joblib.load(models_dir / "deconditioning.joblib"))

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _baseline(history: pd.DataFrame, profile: dict | None) -> dict:
        if profile and profile.get("baseline") and all(v in profile["baseline"] for v in VITAL_SIGNALS):
            return {v: float(profile["baseline"][v]) for v in VITAL_SIGNALS}
        return compute_baseline(history)

    def _rule_alerts(self, last: pd.Series) -> list[dict]:
        alerts, seen = [], set()
        for sig, op, val, level, cond, msg in HARD_LIMITS:   # RED limits are listed first
            if sig in last and OPS[op](last[sig], val) and (sig, cond) not in seen:
                seen.add((sig, cond))
                alerts.append(dict(source="rule", level=level, condition=cond, signal=sig,
                                   value=round(float(last[sig]), 2), threshold=f"{op} {val}", message=msg))
        if last.get("activity_level", 1) < 0.2:
            hr = float(last["heart_rate"])
            if hr >= RESTING_HR_RED:
                alerts.append(dict(source="rule", level="RED", condition="cardiovascular_strain",
                                   signal="heart_rate", value=round(hr, 1), threshold=f">= {RESTING_HR_RED} at rest",
                                   message="Resting heart rate at or above 120 bpm"))
            elif hr >= RESTING_HR_YELLOW:
                alerts.append(dict(source="rule", level="YELLOW", condition="cardiovascular_strain",
                                   signal="heart_rate", value=round(hr, 1), threshold=f">= {RESTING_HR_YELLOW} at rest",
                                   message="Resting heart rate at or above 100 bpm"))
        return alerts

    # ------------------------------------------------------------------ main API
    def assess(self, history: pd.DataFrame, profile: dict | None = None) -> dict:
        """history: hourly rows for ONE astronaut (>= 24 rows recommended), oldest first."""
        history = history.sort_values("timestamp").reset_index(drop=True)
        baseline = self._baseline(history, profile)
        feats = build_features(history, baseline)
        last_raw, last_f = history.iloc[-1], feats.iloc[-1]

        proba_3h = self.risk["model"].predict_proba(feats[self.risk["features"]].tail(3))
        proba = proba_3h.mean(axis=0)
        top = int(np.argmax(proba))
        model_cond, model_p = CONDITIONS[top], float(proba[top])

        a = self.anomaly
        lo, hi = a["scale"]
        raw_3h = -a["model"].score_samples(feats[a["features"]].tail(3))
        anom_3h = np.clip((raw_3h - lo) / (hi - lo), 0, 1)
        anomaly = float(anom_3h[-1])

        # Models alone raise YELLOW. They escalate to RED only when the same condition is
        # highly likely AND highly unusual for this person for 3 consecutive hours.
        model_level = "GREEN"
        if model_cond != "nominal" and model_p >= 0.5:
            sustained = len(proba_3h) == 3 and bool(np.all(proba_3h[:, top] >= 0.9)) \
                and bool(np.all(anom_3h >= 0.9))
            model_level = "RED" if sustained else "YELLOW"
        rules = self._rule_alerts(last_raw)
        rule_level = _worst("GREEN", *[r["level"] for r in rules]) if rules else "GREEN"
        level = _worst(model_level, rule_level)

        alerts = list(rules)
        if model_level != "GREEN":
            alerts.append(dict(source="model", level=model_level, condition=model_cond,
                               probability=round(model_p, 3),
                               message=f"Pattern consistent with {CONDITION_LABELS[model_cond].lower()} "
                                       f"({model_p:.0%} confidence)"))
        alerts.sort(key=lambda x: -LEVEL_RANK[x["level"]])

        # primary condition: the worst RED rule, else the model, else the worst rule
        red_rules = [r for r in rules if r["level"] == "RED"]
        if red_rules:
            condition = red_rules[0]["condition"]
        elif model_level != "GREEN":
            condition = model_cond
        elif rules:
            condition = rules[0]["condition"]
        else:
            condition = "nominal"

        n_red = sum(r["level"] == "RED" for r in rules)
        n_yel = sum(r["level"] == "YELLOW" for r in rules)
        score = 100 - 40 * (1 - float(proba[0])) - 25 * anomaly - 20 * n_red - 8 * n_yel
        score = int(np.clip(round(score), 0, 100))

        # explanation: which vitals moved most vs this person's baseline (in noise units)
        drivers = []
        for v in VITAL_SIGNALS:
            z = float(feats[f"r6_d_{v}"].iloc[-1]) / NOISE_SD[v]
            drivers.append(dict(signal=v, deviation=round(float(feats[f"r6_d_{v}"].iloc[-1]), 2),
                                unit=UNITS[v], z=round(z, 2)))
        drivers = sorted(drivers, key=lambda d: -abs(d["z"]))[:3]

        vitals = {v: dict(value=round(float(last_raw[v]), 2), baseline=round(baseline[v], 2),
                          delta=round(float(last_raw[v]) - baseline[v], 2), unit=UNITS[v])
                  for v in VITAL_SIGNALS}
        summary = self._routine_summary(history)
        actions = actions_for(condition, level) if level != "GREEN" else []

        return {
            "astronaut_id": str(last_raw.get("astronaut_id", "")),
            "timestamp": str(last_raw["timestamp"]),
            "mission_day": int(last_raw.get("mission_day", 0)),
            "status": level,
            "health_score": score,
            "condition": condition,
            "condition_label": CONDITION_LABELS[condition],
            "probabilities": {c: round(float(p), 4) for c, p in zip(CONDITIONS, proba)},
            "anomaly_score": round(anomaly, 3),
            "alerts": alerts,
            "drivers": drivers,
            "vitals": vitals,
            "context": {
                "activity_level": float(last_raw["activity_level"]),
                "is_asleep": int(last_raw["is_asleep"]),
                "cabin_co2_mmhg": round(float(last_raw["cabin_co2_mmhg"]), 2),
                **{k: round(v, 1) for k, v in summary.items()},
            },
            "actions": actions,
            "daily_plan": daily_plan(summary),
            "disclaimer": "Decision support only. Synthetic-data models. The crew medical officer "
                          "and flight surgeon make all medical decisions.",
        }

    @staticmethod
    def _routine_summary(history: pd.DataFrame) -> dict:
        last24, last7d = history.tail(24), history.tail(24 * 7)
        if "exercise_type" in history:
            ared = float((last7d["exercise_type"] == "resistive").sum() * 60)
            aero = float((last7d["exercise_type"] == "aerobic").sum() * 60)
        else:
            ared, aero = 0.0, float((last7d["activity_level"] >= 0.5).sum() * 60)
        return {"sleep_last_24h": float(last24["is_asleep"].sum()),
                "fluid_last_24h": float(last24["fluid_intake_ml"].sum()),
                "ared_minutes_7d": ared, "aerobic_minutes_7d": aero}

    def timeline(self, history: pd.DataFrame, profile: dict | None = None, hours: int = 72) -> list[dict]:
        """Hour-by-hour status for the last `hours` (for charts / replay)."""
        history = history.sort_values("timestamp").reset_index(drop=True)
        baseline = self._baseline(history, profile)
        feats = build_features(history, baseline)
        proba = self.risk["model"].predict_proba(feats[self.risk["features"]])
        a = self.anomaly
        raw = -a["model"].score_samples(feats[a["features"]])
        anom = np.clip((raw - a["scale"][0]) / (a["scale"][1] - a["scale"][0]), 0, 1)
        out = []
        for i in range(max(0, len(history) - hours), len(history)):
            p = proba[max(0, i - 2): i + 1].mean(axis=0)
            top = int(np.argmax(p))
            out.append(dict(timestamp=str(history.loc[i, "timestamp"]), condition=CONDITIONS[top],
                            p_abnormal=round(float(1 - p[0]), 3), anomaly_score=round(float(anom[i]), 3)))
        return out

    # ------------------------------------------------------------------ long-term
    def forecast_deconditioning(self, profile: dict, history: pd.DataFrame | None = None,
                                horizon_days: int = 90, mission_day: int | None = None) -> dict:
        summary = self._routine_summary(history) if history is not None else {}
        ared = summary.get("ared_minutes_7d", profile.get("ared_minutes_week", 0))
        aero = summary.get("aerobic_minutes_7d", profile.get("aerobic_minutes_week", 0))
        if mission_day is None:
            mission_day = int(history["mission_day"].max()) if history is not None else 1

        def rates(ared_min):
            row = pd.DataFrame([{
                "mission_month": max(1, mission_day // 30 + 1), "age": profile["age"],
                "sex_f": int(profile["sex"] == "F"), "ared_minutes_week": ared_min,
                "aerobic_minutes_week": aero, "protein_g_per_kg": profile["protein_g_per_kg"],
                "vitamin_d_ng_ml": profile["vitamin_d_ng_ml"]}])[self.decon["features"]]
            out = {}
            for tgt, ms in self.decon["targets"].items():
                vals = sorted(float(max(ms[k].predict(row)[0], 0)) for k in ("q10", "median", "q90"))
                out[tgt] = dict(zip(("q10", "median", "q90"), vals))
            return out

        cur = rates(ared)
        target = rates(max(ared, ARED_TARGET_MIN_WEEK))
        months_so_far, months_ahead = mission_day / 30.0, (mission_day + horizon_days) / 30.0
        res = {"inputs": {"ared_minutes_7d": ared, "aerobic_minutes_7d": aero, "mission_day": mission_day,
                          "horizon_days": horizon_days}}
        for tgt, name in (("bmd_loss_pct_month", "hip_bmd"), ("muscle_loss_pct_month", "thigh_muscle")):
            r = cur[tgt]
            res[name] = {
                "rate_pct_per_month": {k: round(v, 3) for k, v in r.items()},
                "estimated_loss_to_date_pct": round(r["median"] * months_so_far, 2),
                "projected_loss_pct": {k: round(v * months_ahead, 2) for k, v in r.items()},
                "projected_loss_if_ared_target_met_pct": round(target[tgt]["median"] * months_ahead, 2),
            }
        res["hip_bmd"]["alert"] = res["hip_bmd"]["projected_loss_pct"]["median"] >= BMD_LOSS_ALERT_PCT
        return res

    @staticmethod
    def radiation_status(profile: dict, history: pd.DataFrame, mission: dict) -> dict:
        mission_dose = float(history["radiation_msv"].sum())
        career = float(profile.get("prior_career_dose_msv", 0)) + mission_dose
        day = int(history["mission_day"].max())
        recent = history.tail(24 * 7)["radiation_msv"]
        rate_day = float(recent.sum() / max(len(recent) / 24, 1))
        last24 = float(history.tail(24)["radiation_msv"].sum())
        remaining = max(mission.get("planned_duration_days", day) - day, 0)
        projected = career + rate_day * remaining
        spe = last24 > 3 * mission.get("radiation_msv_per_day_assumed", rate_day)
        return {
            "mission_dose_msv": round(mission_dose, 1),
            "career_dose_msv": round(career, 1),
            "career_limit_msv": CAREER_RADIATION_LIMIT_MSV,
            "career_used_pct": round(100 * career / CAREER_RADIATION_LIMIT_MSV, 1),
            "dose_rate_msv_per_day_7d": round(rate_day, 3),
            "dose_last_24h_msv": round(last24, 2),
            "projected_career_at_mission_end_msv": round(projected, 1),
            "projected_used_pct": round(100 * projected / CAREER_RADIATION_LIMIT_MSV, 1),
            "spe_in_progress": bool(spe),
            "spe_event_limit_msv": SPE_EVENT_LIMIT_MSV,
            "status": "RED" if projected >= CAREER_RADIATION_LIMIT_MSV or spe
                      else "YELLOW" if projected >= 0.8 * CAREER_RADIATION_LIMIT_MSV else "GREEN",
        }
