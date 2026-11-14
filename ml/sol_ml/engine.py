"""Sol Health inference engine v2: statistical, explainable models chosen in notebooks 02-07.

    from sol_ml.engine import HealthEngine
    engine = HealthEngine.load()                       # models/engine_config.json + models/body_iforest.joblib
    result = engine.assess(hourly_df, profile, daily_df)

Parts (parameters come from models/engine_config.json, nothing is hard-coded here except clinical hard limits):
  body       personal robust z (spikes) + CUSUM (slow drifts) + pooled Isolation Forest (odd combinations), daily
  cabin      1-hour / 7-day CO2 means and the rule-based environmental gate
  radiation  dose-rate ratio to the trailing 7-day median (two levels) and the cumulative dose counter
  fitness    change point on the weekly heart rate of the same exercise type
  rules      hard clinical limits (SpO2, temperature, BP, resting HR, CO2, fasting glucose, mood); rules win over models

How the outputs combine: status = the worst level of all active alerts. Models alone raise YELLOW; RED comes from
hard limits and from a solar storm at or above the shelter level. Every alert carries a one-sentence `reason`.
The response keeps the v0 shape (docs/API.md) and adds fields.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import joblib
import numpy as np
import pandas as pd

from .config import (MODELS_DIR, HARD_LIMITS, RESTING_HR_RED, RESTING_HR_YELLOW, VITAL_SIGNALS,
                     CAREER_RADIATION_LIMIT_MSV, SPE_EVENT_LIMIT_MSV, BMD_LOSS_ALERT_PCT, ARED_TARGET_MIN_WEEK,
                     ENGINE_CONDITIONS, ENGINE_CONDITION_LABELS)
from .detectors import cabin, multivariate, univariate
from .detectors.bounded import bounded_cusum
from .detectors import deconditioning as dc
from .detectors import radiation as rad
from .detectors.baseline import BODY_SIGNALS, ORDINAL, to_badness, zscores
from .features import compute_baseline
from .protocols import actions_for, daily_plan

LEVEL_RANK = {"GREEN": 0, "YELLOW": 1, "RED": 2}
OPS = {"<": np.less, ">": np.greater, ">=": np.greater_equal, "<=": np.less_equal}
UNITS = {"heart_rate": "bpm", "hrv_rmssd": "ms", "spo2": "%", "resp_rate": "br/min", "systolic_bp": "mmHg",
         "diastolic_bp": "mmHg", "core_temp": "C", "pvt_reaction_ms": "ms"}
EXERCISE_ACTIVITY = 0.5           # activity level from which an hour counts as exercise
BP_SIGNALS = ("systolic_bp", "diastolic_bp")
DAILY_REPORT_HOUR = 20           # the daily health report leaves for Earth at 20:00 habitat time
DEFAULT_COMM_DELAY_S = 780.0      # Mars-Earth one-way light time used when the mission does not give one
DAILY_AVAILABLE_HOUR = 8          # a day's check-in and night summary are known from 08:00
INDICATORS = {                    # daily indicators: label, unit, column in daily.csv, scale to display
    "resting_hr": ("Resting heart rate", "bpm", "resting_hr", 1.0),
    "sleep_hours": ("Sleep last night", "h", "sleep_minutes", 1 / 60),
    "fatigue": ("Fatigue score", "1-5, 5 = fresh", "fatigue", 1.0),
    "mood": ("Mood score", "1-5, 5 = best", "mood", 1.0),
    "stress": ("Stress score", "1-5, 5 = relaxed", "stress", 1.0),
    "blood_glucose_mg_dl": ("Fasting blood glucose", "mg/dL", "blood_glucose_mg_dl", 1.0),
}
SIGNAL_LABEL = {"resting_hr": "resting heart rate", "sleep_minutes": "sleep", "fatigue": "fatigue score",
                "mood": "mood score", "stress": "stress score"}
WORSE_WORD = {"resting_hr": "above", "sleep_minutes": "below", "fatigue": "worse than", "mood": "worse than", "stress": "worse than"}
RIDGE = {  # NASA Human Research Program hazard behind each condition
    "radiation_event": "Radiation", "co2_exposure": "Hostile / closed environment", "hypoxia": "Hostile / closed environment",
    "fever_infection": "Hostile / closed environment", "low_mood": "Isolation and confinement",
    "unusual_combination": "Isolation and confinement", "sleep_deprivation": "Isolation and confinement",
    "cardiovascular_strain": "Altered gravity", "deconditioning": "Altered gravity", "dehydration": "Altered gravity",
    "physiological_drift": "Distance from Earth", "acute_deviation": "Distance from Earth",
    "low_blood_sugar": "Distance from Earth", "high_blood_sugar": "Distance from Earth",
    "optic_disc_change": "Altered gravity", "kidney_stone_risk": "Altered gravity", "urinary_infection": "Hostile / closed environment",
    "urine_abnormal": "Distance from Earth", "constipation": "Distance from Earth", "diarrhea": "Hostile / closed environment",
    "stool_blood": "Distance from Earth",
}
URINE_SG_CONCENTRATED = 1.030                # specific gravity above this = concentrated urine
DIPSTICK_WORDS = {0: "negative", 1: "trace", 2: "+", 3: "++"}
CONSTIPATION_DAYS, DIARRHEA_MOTIONS = 3, 3
EYE_EXAM_VALID_DAYS = 35                     # an eye-photo result stands until the next monthly photo
GLUCOSE_LIMITS = [("<", 54.0, "RED", "low_blood_sugar", "Fasting glucose below 54 mg/dL"),
                  ("<", 70.0, "YELLOW", "low_blood_sugar", "Fasting glucose below 70 mg/dL"),
                  (">=", 250.0, "RED", "high_blood_sugar", "Fasting glucose at or above 250 mg/dL"),
                  (">=", 126.0, "YELLOW", "high_blood_sugar", "Fasting glucose at or above 126 mg/dL")]
LOW_MOOD_SCORE, LOW_MOOD_DAYS = 2, 3
SYMPTOM_FATIGUE_SCORE = 2
BODY_SYSTEMS = [
    ("heart", "Heart and circulation", "Pumps blood and oxygen to every organ. In weightlessness fluid shifts toward the head and the heart works differently.",
     ["heart_rate", "resting_hr", "systolic_bp", "diastolic_bp", "hrv_rmssd"], {"cardiovascular_strain"}),
    ("lungs", "Lungs and breathing", "Take in oxygen and remove CO2. In a closed cabin CO2 can build up around you in still air.",
     ["spo2", "resp_rate", "cabin_co2_mmhg"], {"hypoxia", "co2_exposure"}),
    ("brain", "Brain, sleep and mood", "Attention, mood and sleep. Isolation, confinement and a shifted day-night cycle wear them down.",
     ["mood", "stress", "fatigue", "sleep_hours", "pvt_reaction_ms"], {"unusual_combination", "low_mood", "sleep_deprivation"}),
    ("bones_muscles", "Bones and muscles", "Carry and move the body. Without gravity they lose mass unless loaded by exercise.",
     ["ared_minutes_7d", "aerobic_minutes_7d", "exercise_heart_rate"], {"deconditioning"}),
    ("blood", "Blood and metabolism", "Carries sugar, fluid and salts. Fluid loss and irregular meals show up here first.",
     ["blood_glucose_mg_dl", "fluid_last_24h"], {"dehydration", "low_blood_sugar", "high_blood_sugar"}),
    ("immune", "Immune system and radiation", "Defends against infection. Radiation and stress weaken it, and a closed cabin spreads germs.",
     ["core_temp", "radiation_dose_rate"], {"fever_infection", "radiation_event"}),
    ("eyes", "Eyes", "In weightlessness fluid shifts toward the head; in some astronauts the optic disc swells and near vision changes (SANS).",
     ["fundus_photo", "vision_change"], {"optic_disc_change"}),
    ("kidneys", "Kidneys and urine", "Filter the blood. Bone loss in space puts extra calcium in the urine, which raises the risk of kidney stones.",
     ["urine_sg", "urine_blood", "urine_leukocytes"], {"kidney_stone_risk", "urinary_infection", "urine_abnormal"}),
    ("gut", "Digestion", "Digests food and absorbs water. Space food, less movement and less fluid change bowel habits.",
     ["stool_bristol", "stool_count", "stool_blood"], {"constipation", "diarrhea", "stool_blood"}),
]
BODY_SIGNAL_SYSTEM = {"urine_sg": "kidneys", "resting_hr": "heart", "sleep_minutes": "brain", "fatigue": "brain", "mood": "brain", "stress": "brain"}


def _worst(*levels):
    return max(levels, key=lambda lv: LEVEL_RANK[lv]) if levels else "GREEN"


def _run_length(flags: np.ndarray, end: int) -> int:
    """How many consecutive True values end at index `end`."""
    n = 0
    while end - n >= 0 and flags[end - n]:
        n += 1
    return n


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


@dataclass
class Prepared:
    """Everything that can be computed once for one astronaut's whole history. All tables are causal:
    row t only uses data up to t, so any earlier moment can be assessed from the same tables (mission replay)."""
    hourly: pd.DataFrame
    daily: pd.DataFrame | None
    profile: dict
    baseline: dict
    body: pd.DataFrame | None
    rad_rate: np.ndarray
    rad_ratio: np.ndarray
    co2_7d: np.ndarray
    day_of_hour: np.ndarray           # index into `daily` available at each hour (-1 = none yet)
    eye_exams: list | None = None     # fundus photos: {date, image, measurements, result}, oldest first


class HealthEngine:
    def __init__(self, config: dict, forest: dict, decon: dict | None = None, sources: dict | None = None,
                 comm_delay_s: float = DEFAULT_COMM_DELAY_S):
        self.config, self.forest, self.decon, self.sources = config, forest, decon, sources or {}
        self.comm_delay_s = float(comm_delay_s)
        members = {m["kind"]: m for m in config["body"]["members"]}
        self.spike, self.combo = members["personal_z"], members["iforest"]
        # notebook 09 re-tunes the drift member for live use (bounded CUSUM); fall back to notebook 02's setting
        self.drift = {**members["cusum"], **config.get("engine", {}).get("drift", {})}
        spe = config["radiation"]["spe_detector"]
        levels = spe.get("levels", {"yellow": spe["threshold"], "red": 2.0})
        self.spe_yellow, self.spe_red, self.spe_window = levels["yellow"], levels["red"], spe["baseline_window_hours"]
        self.quality_factor = config["radiation"]["dose_counter"]["quality_factor"]
        self.fitness = {**config["deconditioning"]["params"], **config.get("engine", {}).get("fitness", {})}
        rules = config.get("engine", {}).get("rules", {})
        self.low_mood_score, self.low_mood_days = rules.get("low_mood_score", LOW_MOOD_SCORE), rules.get("low_mood_days", LOW_MOOD_DAYS)

    @classmethod
    def load(cls, models_dir=MODELS_DIR, demo_dir=None) -> "HealthEngine":
        config = json.loads((models_dir / "engine_config.json").read_text())
        decon_path = models_dir / "deconditioning.joblib"
        sources = {}
        if demo_dir is not None and (demo_dir / "sources.json").exists():
            sources = json.loads((demo_dir / "sources.json").read_text())
        return cls(config, joblib.load(models_dir / "body_iforest.joblib"),
                   joblib.load(decon_path) if decon_path.exists() else None, sources)

    # ------------------------------------------------------------------ preparation (causal tables)
    def body_table(self, daily: pd.DataFrame) -> pd.DataFrame:
        """Per day: personal z-scores, CUSUM sums, and the three body flags."""
        X = to_badness(daily).to_numpy(float)
        out = pd.DataFrame(index=daily.index)
        z_spike, z_drift, z_combo = (zscores(X, m["window"]) for m in (self.spike, self.drift, self.combo))
        sums = bounded_cusum(z_drift[:, :3], self.drift["k"], self.drift.get("cap"), self.drift.get("z_clip"))
        for j, s in enumerate(BODY_SIGNALS):
            out[f"z_{s}"] = z_spike[:, j]
            out[f"zd_{s}"] = z_drift[:, j]
            out[f"zc_{s}"] = z_combo[:, j]
        for j, s in enumerate(BODY_SIGNALS[:3]):
            out[f"cusum_{s}"] = sums[:, j]
        out["spike"] = univariate.threshold_alerts(z_spike, self.spike["thr"], self.spike.get("sided", "worse"))
        out["drift"] = (sums > self.drift["h"]).any(axis=1)
        filled, ok = multivariate.prepare(z_combo)
        scores = self.forest["model"].model.score_samples(filled)
        out["combo"] = multivariate.worse_only((scores < self.forest["model"].threshold) & ok, z_combo)
        rank = np.searchsorted(self.forest["train_scores"], scores) / len(self.forest["train_scores"])
        out["unusual"] = np.where(ok, 1.0 - rank, 0.0)          # 1 = more isolated than every real training day
        return out

    @staticmethod
    def grade_eye_exams(exams: list[dict]) -> list[dict]:
        """Measure each photo (bytes under `png`, or measurements already given) and compare it with the first usable one."""
        from . import fundus
        graded, baseline = [], None
        for e in sorted(exams, key=lambda x: x["date"]):
            m = e.get("measurements") or fundus.measure(e["png"])
            result = fundus.compare(m, baseline)
            if baseline is None and m["usable"]:
                baseline = m
            graded.append({k: v for k, v in e.items() if k != "png"} | {"measurements": m, "result": result})
        return graded

    def prepare(self, hourly: pd.DataFrame, profile: dict | None = None, daily: pd.DataFrame | None = None,
                eye_exams: list[dict] | None = None) -> Prepared:
        hourly = hourly.sort_values("timestamp").reset_index(drop=True)
        profile = profile or {}
        if profile.get("baseline") and all(v in profile["baseline"] for v in VITAL_SIGNALS):
            baseline = {v: float(profile["baseline"][v]) for v in VITAL_SIGNALS}
        else:
            baseline = compute_baseline(hourly)
        if "radiation_ugy_per_day" in hourly:
            rate = hourly["radiation_ugy_per_day"].to_numpy(float)
        else:                                               # mSv per hour -> absorbed dose rate in uGy/day
            rate = hourly["radiation_msv"].to_numpy(float) * 24 * 1000 / self.quality_factor
        ratio = np.nan_to_num(rad.spe_score(rate, "ratio", self.spe_window), nan=1.0)
        co2_7d = cabin.rolling_mean(hourly["cabin_co2_mmhg"].to_numpy(float))
        body, day_of_hour = None, np.full(len(hourly), -1)
        if daily is not None and len(daily):
            daily = daily.sort_values("date").reset_index(drop=True)
            body = self.body_table(daily)
            ts = hourly["timestamp"]
            known = (ts - pd.Timedelta(hours=DAILY_AVAILABLE_HOUR)).dt.normalize()
            day_of_hour = np.searchsorted(pd.to_datetime(daily["date"]).to_numpy(), known.to_numpy(), side="right") - 1
        return Prepared(hourly, daily, profile, baseline, body, rate, ratio, co2_7d, day_of_hour,
                        self.grade_eye_exams(eye_exams) if eye_exams else None)

    # ------------------------------------------------------------------ alert builders
    def _alert(self, source, level, condition, message, reason, kind, **extra) -> dict:
        return dict(source=source, level=level, condition=condition, message=message, reason=reason, kind=kind,
                    hazard=RIDGE.get(condition, "Distance from Earth"), **extra)

    def _rule_alerts(self, prep: Prepared, i: int) -> list[dict]:
        h, last = prep.hourly, prep.hourly.iloc[i]
        alerts, seen = [], set()
        exercising = last.get("activity_level", 0) >= EXERCISE_ACTIVITY
        asleep = int(last.get("is_asleep", 0)) == 1
        for sig, op, val, level, cond, msg in HARD_LIMITS:      # RED limits are listed first
            if sig in BP_SIGNALS and (exercising or asleep):     # blood pressure is judged awake and at rest:
                continue                                         # it rises in exercise and dips in sleep
            if sig in last and OPS[op](last[sig], val) and (sig, cond) not in seen:
                seen.add((sig, cond))
                hours = _run_length(OPS[op](h[sig].to_numpy(float)[: i + 1], val), i)
                unit = UNITS.get(sig, "mmHg")
                alerts.append(self._alert("rule", level, cond, msg,
                                          f"{msg}: now {float(last[sig]):.1f} {unit}, for {_plural(hours, 'hour')}.", "hard_limit",
                                          signal=sig, value=round(float(last[sig]), 2), threshold=f"{op} {val}"))
        if last.get("activity_level", 1) < 0.2 and i >= 1:
            # a wearable's hourly heart rate must stay high at rest for two hours in a row (one hour is often movement)
            hr = float(last["heart_rate"])
            prev_rest = float(h["activity_level"].iloc[i - 1]) < 0.2
            hr_prev = float(h["heart_rate"].iloc[i - 1]) if prev_rest else 0.0
            for limit, level in ((RESTING_HR_RED, "RED"), (RESTING_HR_YELLOW, "YELLOW")):
                if hr >= limit and hr_prev >= limit:
                    msg = f"Resting heart rate at or above {limit:.0f} bpm"
                    alerts.append(self._alert("rule", level, "cardiovascular_strain", msg,
                                              f"{msg}: {hr:.0f} bpm at rest this hour and {hr_prev:.0f} bpm the hour before.", "hard_limit",
                                              signal="heart_rate", value=round(hr, 1), threshold=f">= {limit:.0f} at rest"))
                    break
        return alerts

    def _daily_rule_alerts(self, prep: Prepared, d: int) -> list[dict]:
        alerts, daily = [], prep.daily
        glucose = daily["blood_glucose_mg_dl"].iloc[d] if "blood_glucose_mg_dl" in daily else np.nan
        if pd.notna(glucose):
            for op, val, level, cond, msg in GLUCOSE_LIMITS:
                if OPS[op](glucose, val):
                    alerts.append(self._alert("rule", level, cond, msg, f"{msg}: this morning's reading is {glucose:.0f} mg/dL.",
                                              "hard_limit", signal="blood_glucose_mg_dl", value=float(glucose), threshold=f"{op} {val:.0f}"))
                    break
        alerts += self._urine_stool_alerts(daily, d)
        if "mood" in daily:
            low = (daily["mood"].to_numpy(float)[: d + 1] <= self.low_mood_score)
            days = _run_length(low, d)
            if days >= self.low_mood_days:
                alerts.append(self._alert("rule", "YELLOW", "low_mood", "Low mood for several days",
                                          f"Mood score has been {self.low_mood_score} or lower (5 = best) for {_plural(days, 'day')} in a row.",
                                          "mood", signal="mood", value=float(daily['mood'].iloc[d]),
                                          threshold=f"<= {self.low_mood_score} for {self.low_mood_days} days"))
        return alerts

    def _urine_stool_alerts(self, daily: pd.DataFrame, d: int) -> list[dict]:
        """Rules for this morning's urine dipstick and stool log (clinical rules, no learned model)."""
        if "urine_sg" not in daily:
            return []
        out, row = [], daily.iloc[d]
        val = lambda k: row.get(k, np.nan)
        if pd.notna(val("urine_sg")) and val("urine_sg") > URINE_SG_CONCENTRATED:
            out.append(self._alert("rule", "YELLOW", "dehydration", "Concentrated urine",
                                   f"Your urine specific gravity is {val('urine_sg'):.3f}, above {URINE_SG_CONCENTRATED:.3f}: you are probably not drinking enough.",
                                   "urine", signal="urine_sg", value=float(val("urine_sg")), threshold=f"> {URINE_SG_CONCENTRATED:.3f}"))
        if pd.notna(val("urine_blood")) and val("urine_blood") >= 2:
            pain = val("flank_pain") == 1
            out.append(self._alert("rule", "RED" if pain else "YELLOW", "kidney_stone_risk", "Blood in urine",
                                   f"Your urine dipstick shows blood ({DIPSTICK_WORDS[int(val('urine_blood'))]})"
                                   + (" and you reported pain in your side or back: possible kidney stone." if pain else ": with bone loss in space this can mean a kidney stone starting."),
                                   "urine", signal="urine_blood", value=float(val("urine_blood")), threshold=">= +"))
        if pd.notna(val("urine_leukocytes")) and val("urine_leukocytes") >= 2 and val("urine_nitrite") == 1:
            out.append(self._alert("rule", "YELLOW", "urinary_infection", "Possible urinary infection",
                                   f"Your urine dipstick shows white cells ({DIPSTICK_WORDS[int(val('urine_leukocytes'))]}) and nitrite: a sign of a urinary infection.",
                                   "urine", signal="urine_leukocytes", value=float(val("urine_leukocytes")), threshold=">= + with nitrite"))
        for pad, name in (("urine_protein", "protein"), ("urine_glucose", "sugar"), ("urine_ketones", "ketones")):
            if pd.notna(val(pad)) and val(pad) >= 2:
                out.append(self._alert("rule", "YELLOW", "urine_abnormal", f"{name.capitalize()} in urine",
                                       f"Your urine dipstick shows {name} ({DIPSTICK_WORDS[int(val(pad))]}); it is normally negative.",
                                       "urine", signal=pad, value=float(val(pad)), threshold=">= +"))
        if "stool_bristol" in daily:
            hard = daily["stool_bristol"].to_numpy(float)[: d + 1] <= 2
            days = _run_length(hard, d)
            if days >= CONSTIPATION_DAYS:
                out.append(self._alert("rule", "YELLOW", "constipation", "Constipation",
                                       f"Your stool has been hard (Bristol type 1-2) for {_plural(days, 'day')} in a row.",
                                       "stool", signal="stool_bristol", value=float(val("stool_bristol")), threshold=f"type <= 2 for {CONSTIPATION_DAYS} days"))
            if pd.notna(val("stool_bristol")) and val("stool_bristol") >= 6 and val("stool_count") >= DIARRHEA_MOTIONS:
                out.append(self._alert("rule", "YELLOW", "diarrhea", "Diarrhoea",
                                       f"You logged {int(val('stool_count'))} loose stools (Bristol type {int(val('stool_bristol'))}) today: watch your fluids.",
                                       "stool", signal="stool_bristol", value=float(val("stool_bristol")), threshold=f"type >= 6, {DIARRHEA_MOTIONS}+ a day"))
            if val("stool_blood") == 1:
                out.append(self._alert("rule", "YELLOW", "stool_blood", "Blood in stool",
                                       "You reported blood in your stool today; your flight surgeon sees this in today's report.",
                                       "stool", signal="stool_blood", value=1.0, threshold="any visible blood"))
        return out

    def _eye_alert(self, prep: Prepared, i: int) -> dict | None:
        """The latest fundus photo up to this hour, compared with the baseline photo (sol_ml.fundus)."""
        exams = getattr(prep, "eye_exams", None) or []
        now = prep.hourly["timestamp"].iloc[i]
        done = [e for e in exams if pd.Timestamp(e["date"]) <= now]
        if not done:
            return None
        last = done[-1]
        result = last.get("result") or {}
        if result.get("level", "GREEN") == "GREEN" or (now - pd.Timestamp(last["date"])).days > EYE_EXAM_VALID_DAYS:
            return None
        if result.get("kind") == "retake":
            return None                       # a bad photo is a question (retake it), not a health alert
        vision = prep.daily is not None and "vision_change" in prep.daily and int(prep.day_of_hour[i]) >= 0 \
            and prep.daily["vision_change"].iloc[int(prep.day_of_hour[i])] == 1
        level = "RED" if vision else result["level"]
        reason = result["reason"] + (" You also reported a change in your vision." if vision else "")
        return self._alert("model", level, "optic_disc_change", "Eye photo: optic disc changed", reason, "eye_exam",
                           signal="fundus_photo", value=result.get("ratios", {}).get("margin_sharpness"),
                           threshold="margin sharpness < 75 % of baseline (watch), < 55 % or disc +35 % (act now)",
                           probability=0.5, model="fundus photo measurement against your baseline photo (no trained model)")

    def _body_alerts(self, prep: Prepared, d: int) -> list[dict]:
        body, daily, alerts = prep.body, prep.daily, []
        row = body.iloc[d]
        spike = None                     # (signal, robust z, days) of today's spike, if any
        if row["spike"]:
            z = {s: row[f"z_{s}"] for s in BODY_SIGNALS}
            s = max(z, key=lambda k: -np.inf if np.isnan(z[k]) else z[k])
            days = _run_length(body["spike"].to_numpy(bool), d)
            spike = (s, float(z[s]), days)
            alerts.append(self._alert(
                "model", "YELLOW", "acute_deviation", f"Unusual {SIGNAL_LABEL[s]} for you",
                f"{SIGNAL_LABEL[s].capitalize()} is {z[s]:.1f} robust SD {WORSE_WORD[s]} your {self.spike['window']}-day normal, "
                f"for {_plural(days, 'day')}.", "spike", signal=s, z=round(float(z[s]), 2), value=float(daily[s].iloc[d]),
                probability=round(float(min(z[s] / (2 * self.spike['thr']), 1.0)), 3), model="personal robust z"))
        if row["drift"]:
            sums = {s: row[f"cusum_{s}"] for s in BODY_SIGNALS[:3]}
            s = max(sums, key=sums.get)
            col = body[f"cusum_{s}"].to_numpy(float)
            rising = _run_length(col[: d + 1] > 0, d)
            recent = body[f"zd_{s}"].iloc[max(0, d - rising + 1): d + 1].mean()
            active = _run_length(body["drift"].to_numpy(bool), d)
            alerts.append(self._alert(
                "model", "YELLOW", "physiological_drift", f"Slow drift in {SIGNAL_LABEL[s]}",
                f"{SIGNAL_LABEL[s].capitalize()} has been {WORSE_WORD[s]} your {self.drift['window']}-day normal for {_plural(rising, 'day')} "
                f"(average {recent:.1f} robust SD); the alert has been active for {_plural(active, 'day')}.", "drift",
                signal=s, z=round(float(recent), 2), value=float(daily[s].iloc[d]), cusum=round(float(sums[s]), 2),
                probability=round(float(min(sums[s] / (2 * self.drift['h']), 1.0)), 3), model="CUSUM on personal z"))
        if row["combo"]:
            z = {s: row[f"zc_{s}"] for s in BODY_SIGNALS if not np.isnan(row[f"zc_{s}"])}
            top = sorted(z, key=lambda k: -z[k])[:3]
            days = _run_length(body["combo"].to_numpy(bool), d)
            if spike and spike[0] in top:
                # Both detectors point at the same signal today: one alert, not two, naming the far-out signal
                # and the ones that moved with it.
                s, zs, sdays = spike
                others = [o for o in top if o != s and z[o] > 0]
                with_it = (f", and {', '.join(f'{SIGNAL_LABEL[o]} ({z[o]:+.1f} SD)' for o in others)} moved with it"
                           if others else "")
                alerts = [a for a in alerts if a["kind"] != "spike"]   # the spike alert added above
                alerts.append(self._alert(
                    "model", "YELLOW", "unusual_combination", f"Unusual {SIGNAL_LABEL[s]} for you",
                    f"{SIGNAL_LABEL[s].capitalize()} is {zs:.1f} robust SD {WORSE_WORD[s]} your {self.spike['window']}-day normal"
                    f"{with_it}, for {_plural(max(sdays, days), 'day')}.", "combination",
                    signal=s, z=round(zs, 2), value=float(daily[s].iloc[d]), far_out=True,
                    with_signals=[{"signal": o, "z": round(float(z[o]), 2)} for o in others],
                    probability=round(float(max(row["unusual"], min(zs / (2 * self.spike["thr"]), 1.0))), 3),
                    model="personal robust z + Isolation Forest on the daily z-vector"))
            else:
                parts = ", ".join(f"{SIGNAL_LABEL[s]} {z[s]:+.1f} SD" for s in top if z[s] > 0)
                tail = "" if spike else "; no single signal is far out on its own"
                alerts.append(self._alert(
                    "model", "YELLOW", "unusual_combination", "Unusual combination of signals",
                    f"Today's combination is unusual for you ({parts}; positive = worse), for {_plural(days, 'day')}{tail}.",
                    "combination", signal=top[0], z=round(float(z[top[0]]), 2), far_out=bool(spike),
                    with_signals=[{"signal": o, "z": round(float(z[o]), 2)} for o in top[1:] if z[o] > 0],
                    probability=round(float(row['unusual']), 3), model="Isolation Forest on the daily z-vector"))
        return alerts

    def _cabin_alert(self, prep: Prepared, i: int, d: int) -> tuple[dict | None, dict]:
        one, seven = float(prep.hourly["cabin_co2_mmhg"].iloc[i]), float(prep.co2_7d[i])
        high = bool(cabin.co2_high(np.array([one]), np.array([seven]))[0])
        ctx = {"cabin_co2_7d_mean_mmhg": None if np.isnan(seven) else round(seven, 2), "cabin_co2_high": high}
        if not high or d < 0:
            return None, ctx
        today = prep.daily.iloc[d]
        symptoms = [name for name, hit in (("headache", today.get("headache", 0) == 1),
                                           ("fatigue", today.get("fatigue", 5) <= SYMPTOM_FATIGUE_SCORE)) if hit]
        if not symptoms:
            return None, ctx
        text = cabin.reason(one, seven if not np.isnan(seven) else 0.0)
        alert = self._alert("rule", "YELLOW", "co2_exposure", "Likely environmental: cabin CO2 is high",
                            f"You reported {' and '.join(symptoms)} while " + text[0].lower() + text[1:], "environmental_gate",
                            signal="cabin_co2_mmhg", value=round(one, 2),
                            threshold=f"1-h > {cabin.LIMIT_1H_MMHG:g} or 7-day > {cabin.LIMIT_7D_MMHG:g} mmHg, with symptoms")
        return alert, ctx

    def _spe(self, prep: Prepared, i: int) -> dict:
        ratio = float(prep.rad_ratio[i])
        level = "RED" if ratio >= self.spe_red else "YELLOW" if ratio >= self.spe_yellow else "GREEN"
        hours = _run_length(prep.rad_ratio[: i + 1] >= self.spe_yellow, i)
        return {"ratio": ratio, "level": level, "hours": hours}

    def _spe_alert(self, spe: dict) -> dict | None:
        if spe["level"] == "GREEN":
            return None
        shelter = spe["level"] == "RED"
        message = "Solar storm in progress: go to the storm shelter now" if shelter else "Radiation elevated: prepare the storm shelter"
        return self._alert("model", spe["level"], "radiation_event", message,
                           f"Radiation dose rate is {spe['ratio']:.1f} times the 7-day normal and has been elevated for "
                           f"{_plural(spe['hours'], 'hour')}.", "spe", signal="radiation_dose_rate", value=round(spe["ratio"], 2),
                           threshold=f">= {self.spe_yellow:g}x (elevated), >= {self.spe_red:g}x (shelter)",
                           probability=round(min(spe["ratio"] / (2 * self.spe_red), 1.0), 3), model="ratio to the trailing 7-day median")

    def fitness_trend(self, hourly: pd.DataFrame) -> dict:
        """Change point on the weekly heart rate of the same exercise type (notebook 03, model D)."""
        ex = hourly[hourly["exercise_type"].ne("none")] if "exercise_type" in hourly else hourly.iloc[:0]
        out = {"alert": False, "shift_bpm": 0.0, "weeks_ago": 0, "sessions": int(len(ex)),
               "reason": "Not enough exercise sessions yet to judge a fitness trend."}
        if len(ex) < 12:
            return out
        day = ex["mission_day"] if "mission_day" in ex else ((ex["timestamp"] - hourly["timestamp"].iloc[0]).dt.days + 1)
        sessions = pd.DataFrame({"week": ((day - 1) // 7).astype(int).to_numpy(), "activity": ex["exercise_type"].to_numpy(),
                                 "avg_hr": ex["heart_rate"].to_numpy(float)})
        shift, weeks_ago = dc.changepoint_stat(sessions, int(sessions["week"].max()), self.fitness["penalty"])
        if np.isnan(shift):
            return out
        alert = bool(dc.changepoint_alerts(np.array([[shift, weeks_ago]]), self.fitness["thr"])[0])
        out.update(alert=alert, shift_bpm=round(float(shift), 1), weeks_ago=int(weeks_ago),
                   reason=(f"Heart rate in the same exercise types has been {shift:.0f} bpm higher for the last {_plural(int(weeks_ago), 'week')}."
                           if alert else "Exercise heart rate is stable for the same exercise types."))
        return out

    # ------------------------------------------------------------------ main API
    def assess(self, history: pd.DataFrame, profile: dict | None = None, daily: pd.DataFrame | None = None) -> dict:
        """history: hourly rows for ONE astronaut, oldest first. daily: that astronaut's daily table (optional;
        without it only the hard limits, the cabin and the radiation parts run)."""
        prep = self.prepare(history, profile, daily)
        return self.assess_at(prep, len(prep.hourly) - 1)

    def collect_alerts(self, prep: Prepared, i: int) -> tuple[list[dict], dict, dict, int]:
        d = int(prep.day_of_hour[i])
        alerts = self._rule_alerts(prep, i)
        gate, cabin_ctx = self._cabin_alert(prep, i, d)
        if d >= 0:
            alerts += self._daily_rule_alerts(prep, d) + self._body_alerts(prep, d)
        if gate:
            alerts.append(gate)
            for a in alerts:                 # a fatigue-driven body alert during high CO2 is probably the cabin
                if a["kind"] in ("spike", "drift") and a.get("signal") == "fatigue":
                    a["reason"] += " Cabin CO2 is high: likely environmental."
        eye = self._eye_alert(prep, i)
        if eye:
            alerts.append(eye)
        spe = self._spe(prep, i)
        spe_alert = self._spe_alert(spe)
        if spe_alert:
            alerts.append(spe_alert)
        alerts.sort(key=lambda a: -LEVEL_RANK[a["level"]])
        return alerts, cabin_ctx, spe, d

    def assess_at(self, prep: Prepared, i: int, light: bool = False) -> dict:
        """Assessment at hourly row i, using only data up to that hour. light=True skips the slow extras (timeline)."""
        h = prep.hourly
        last = h.iloc[i]
        alerts, cabin_ctx, spe, d = self.collect_alerts(prep, i)
        level = _worst("GREEN", *[a["level"] for a in alerts])
        unusual = float(prep.body["unusual"].iloc[d]) if d >= 0 else 0.0
        weights = {c: 0.0 for c in ENGINE_CONDITIONS}
        for a in alerts:
            weights[a["condition"]] += 3.0 if a["level"] == "RED" else 2.0
        weights["nominal"] = 1.0 if alerts else 1.0 + 1e-9
        total = sum(weights.values())
        probabilities = {c: round(w / total, 4) for c, w in weights.items()}
        condition = alerts[0]["condition"] if alerts else "nominal"
        if light:
            return {"timestamp": str(last["timestamp"]), "status": level, "condition": condition,
                    "p_abnormal": round(1 - probabilities["nominal"], 3), "anomaly_score": round(unusual, 3)}

        fitness = self.fitness_trend(h.iloc[: i + 1])
        if fitness["alert"]:
            alerts.append(self._alert("model", "YELLOW", "deconditioning", "Fitness may be slipping", fitness["reason"], "fitness_trend",
                                      signal="exercise_heart_rate", value=fitness["shift_bpm"], threshold=f">= {self.fitness['thr']:g} bpm shift",
                                      probability=0.5, model="change point (PELT) on weekly exercise heart rate"))
            level = _worst(level, "YELLOW")
            condition = condition if condition != "nominal" else "deconditioning"
            weights["deconditioning"] += 2.0
            total = sum(weights.values())
            probabilities = {c: round(w / total, 4) for c, w in weights.items()}
        n_red = sum(a["level"] == "RED" for a in alerts)
        n_yel = sum(a["level"] == "YELLOW" for a in alerts)
        score = int(np.clip(round(100 - 22 * n_red - 9 * n_yel - 15 * unusual), 0, 100))

        src = lambda name: self.sources.get(name, {"kind": "simulated"})
        vitals = {v: dict(value=round(float(last[v]), 2), baseline=round(prep.baseline[v], 2),
                          delta=round(float(last[v]) - prep.baseline[v], 2), unit=UNITS[v], source=src(v)) for v in VITAL_SIGNALS}
        indicators, drivers = {}, []
        if d >= 0:
            today, body = prep.daily.iloc[d], prep.body.iloc[d]
            for name, (label, unit, col, k) in INDICATORS.items():
                if col not in prep.daily or pd.isna(today[col]):
                    continue
                past = prep.daily[col].iloc[max(0, d - 14): d].dropna()
                base = float(past.median()) * k if len(past) else None
                z = body.get(f"z_{col}")
                indicators[name] = dict(label=label, value=round(float(today[col]) * k, 2), baseline=None if base is None else round(base, 2),
                                        delta=None if base is None else round(float(today[col]) * k - base, 2), unit=unit,
                                        z=None if z is None or np.isnan(z) else round(float(z), 2), date=str(today["date"])[:10], source=src(col))
            for s in BODY_SIGNALS:
                z = body[f"z_{s}"]
                if not np.isnan(z):
                    past = prep.daily[s].iloc[max(0, d - 14): d].dropna()
                    drivers.append(dict(signal=s, deviation=round(float(today[s] - past.median()), 2) if len(past) else 0.0,
                                        unit={"resting_hr": "bpm", "sleep_minutes": "min"}.get(s, "points"), z=round(float(z), 2)))
            drivers = sorted(drivers, key=lambda x: -x["z"])[:3]      # positive z = worse than your normal

        summary = self._routine_summary(h.iloc[: i + 1])
        actions, seen = [], set()
        for a in alerts:
            for act in actions_for(a["condition"], a["level"]):
                key = (act["who"], act["action"])
                if key not in seen:
                    seen.add(key)
                    actions.append(act)
        actions.sort(key=lambda a: (-LEVEL_RANK[a["level"]], a["priority"]))
        for n, a in enumerate(actions, 1):
            a["priority"] = n

        return {
            "astronaut_id": str(last.get("astronaut_id", "")),
            "timestamp": str(last["timestamp"]),
            "mission_day": int(last.get("mission_day", 0)),
            "status": level,
            "health_score": score,
            "condition": condition,
            "condition_label": ENGINE_CONDITION_LABELS[condition],
            "probabilities": probabilities,
            "anomaly_score": round(unusual, 3),
            "alerts": alerts,
            "drivers": drivers,
            "vitals": vitals,
            "indicators": indicators,
            "body_systems": self._body_systems(alerts, fitness),
            "context": {
                "activity_level": float(last["activity_level"]),
                "is_asleep": int(last["is_asleep"]),
                "cabin_co2_mmhg": round(float(last["cabin_co2_mmhg"]), 2),
                **{k: round(v, 1) for k, v in summary.items()},
                **cabin_ctx,
                "radiation_ratio_to_7d": round(spe["ratio"], 2),
                "radiation_level": spe["level"],
            },
            "actions": actions,
            "daily_plan": daily_plan(summary),
            "fitness_trend": fitness,
            "escalation": self.escalation(alerts, last["timestamp"]),
            "disclaimer": "Decision support only. The astronaut is simulated; models are statistical and were tuned on real PMData, "
                          "MSL RAD and ISS cabin data. Your flight surgeon makes all medical decisions.",
        }

    def escalation(self, alerts: list[dict], timestamp) -> dict:
        """What reaches the flight surgeon on Earth. A RED alert is sent at once and arrives after the communication delay;
        YELLOW alerts go in the daily report; with no alert nothing is sent."""
        ts = pd.Timestamp(timestamp)
        red = [a for a in alerts if a["level"] == "RED"]
        to = "Your flight surgeon"
        if red:
            arrives = ts + pd.Timedelta(seconds=self.comm_delay_s)
            return {"status": "sent", "to": to, "level": "RED", "sent_at": str(ts), "arrives_at": str(arrives),
                    "summary": f"Sent at once: {red[0]['message']}. It reaches Earth about {round(self.comm_delay_s / 60)} minutes after sending.",
                    "items": [a["reason"] for a in alerts]}
        if alerts:
            report = ts.normalize() + pd.Timedelta(hours=DAILY_REPORT_HOUR)
            if ts >= report:
                report += pd.Timedelta(days=1)
            return {"status": "daily_report", "to": to, "level": "YELLOW", "sent_at": str(report),
                    "arrives_at": str(report + pd.Timedelta(seconds=self.comm_delay_s)),
                    "summary": f"Included in your daily report to the flight surgeon at {report:%H:%M}.",
                    "items": [a["reason"] for a in alerts]}
        return {"status": "none", "to": to, "level": "GREEN", "sent_at": None, "arrives_at": None,
                "summary": "Nothing needs your flight surgeon right now.", "items": []}

    @staticmethod
    def _body_systems(alerts: list[dict], fitness: dict) -> list[dict]:
        out = []
        for sid, label, function, indicators, conditions in BODY_SYSTEMS:
            mine = [a for a in alerts if a["condition"] in conditions
                    or (a["kind"] in ("spike", "drift") and BODY_SIGNAL_SYSTEM.get(a.get("signal")) == sid)]
            status = _worst("GREEN", *[a["level"] for a in mine])
            summary = mine[0]["reason"] if mine else ("Within your normal range." if sid != "bones_muscles" else fitness["reason"])
            out.append(dict(id=sid, label=label, function=function, status=status, summary=summary, indicators=indicators,
                            alerts=[a["message"] for a in mine]))
        return out

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

    def timeline(self, history: pd.DataFrame, profile: dict | None = None, hours: int = 72,
                 daily: pd.DataFrame | None = None, prep: Prepared | None = None, end: int | None = None) -> list[dict]:
        """Hour-by-hour status for the last `hours` (for charts / replay)."""
        prep = prep or self.prepare(history, profile, daily)
        end = len(prep.hourly) - 1 if end is None else end
        return [self.assess_at(prep, i, light=True) for i in range(max(0, end - hours + 1), end + 1)]

    # ------------------------------------------------------------------ long-term
    def forecast_deconditioning(self, profile: dict, history: pd.DataFrame | None = None,
                                horizon_days: int = 90, mission_day: int | None = None) -> dict:
        """Bone / muscle projection (v0 quantile model, trained on a SIMULATED cohort from published loss rates)
        plus the data-driven fitness trend from exercise heart rate."""
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
        res["fitness_trend"] = self.fitness_trend(history) if history is not None else None
        res["source"] = {"kind": "simulated", "calibrated_on": "published bone and muscle loss rates (model trained on a simulated cohort)"}
        return res

    def radiation_status(self, profile: dict, history: pd.DataFrame, mission: dict, prep: Prepared | None = None,
                         end: int | None = None) -> dict:
        prep = prep or self.prepare(history, profile)
        end = len(prep.hourly) - 1 if end is None else end
        h = prep.hourly.iloc[: end + 1]
        mission_dose = float(h["radiation_msv"].sum())
        career = float(profile.get("prior_career_dose_msv", 0)) + mission_dose
        day = int(h["mission_day"].max())
        recent = h.tail(24 * 7)["radiation_msv"]
        rate_day = float(recent.sum() / max(len(recent) / 24, 1))
        last24 = float(h.tail(24)["radiation_msv"].sum())
        remaining = max(mission.get("planned_duration_days", day) - day, 0)
        assumed = mission.get("radiation_msv_per_day_assumed", rate_day)
        projected = career + assumed * remaining
        spe = self._spe(prep, end)
        budget = rad.dose_status(projected, CAREER_RADIATION_LIMIT_MSV)
        alert = self._spe_alert(spe)
        return {
            "mission_dose_msv": round(mission_dose, 1),
            "career_dose_msv": round(career, 1),
            "career_limit_msv": CAREER_RADIATION_LIMIT_MSV,
            "career_used_pct": round(100 * career / CAREER_RADIATION_LIMIT_MSV, 1),
            "dose_rate_msv_per_day_7d": round(rate_day, 3),
            "dose_last_24h_msv": round(last24, 2),
            "projected_career_at_mission_end_msv": round(projected, 1),
            "projected_used_pct": round(100 * projected / CAREER_RADIATION_LIMIT_MSV, 1),
            "spe_in_progress": spe["level"] != "GREEN",
            "spe_event_limit_msv": SPE_EVENT_LIMIT_MSV,
            "status": _worst(spe["level"], budget),
            "spe_level": spe["level"],
            "dose_rate_ratio_to_7d": round(spe["ratio"], 2),
            "dose_rate_ugy_per_day": round(float(prep.rad_rate[end]), 1),
            "budget_status": budget,
            "quality_factor": self.quality_factor,
            "reason": alert["reason"] if alert else f"Dose rate is {spe['ratio']:.2f} times the 7-day normal: no solar particle event.",
            "action": alert["message"] if alert else None,
            "source": self.sources.get("radiation_ugy_per_day", {"kind": "simulated"}),
        }
