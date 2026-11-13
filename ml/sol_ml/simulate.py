"""Synthetic astronaut data generator.

Real astronaut medical data is private, so Sol Health trains on physiologically
plausible synthetic data. Everything here is a simulation with documented assumptions
(see docs/DATA_DICTIONARY.md and docs/MODELS.md). Do not present it as real crew data.

Two generators:
  * simulate_astronaut()   -> hourly telemetry with injected health episodes (labels)
  * simulate_deconditioning_cohort() -> weekly bone / muscle records for the forecaster
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict

import numpy as np
import pandas as pd

from .config import CONDITIONS, DEMO_DIR, BASELINE_DAYS

MISSION_START = pd.Timestamp("2026-08-31 00:00:00")

# Per-unit-intensity physiological signature of each condition.
# Keys are signal deltas added on top of the astronaut's normal physiology.
SIGNATURES = {
    "sleep_deprivation": {"heart_rate": 6, "hrv_rmssd": -15, "pvt_reaction_ms": 70,
                          "resp_rate": 0.5, "core_temp": -0.1},
    "dehydration": {"heart_rate": 14, "systolic_bp": -14, "diastolic_bp": -6,
                    "hrv_rmssd": -10, "core_temp": 0.35, "pvt_reaction_ms": 20},
    "co2_exposure": {"resp_rate": 4, "heart_rate": 6, "pvt_reaction_ms": 35, "systolic_bp": 4},
    "cardiovascular_strain": {"heart_rate": 22, "systolic_bp": 26, "diastolic_bp": 12,
                              "hrv_rmssd": -22},
    "fever_infection": {"core_temp": 1.6, "heart_rate": 18, "resp_rate": 4, "hrv_rmssd": -18,
                        "spo2": -1.0, "pvt_reaction_ms": 40},
    "hypoxia": {"spo2": -7, "resp_rate": 6, "heart_rate": 14, "pvt_reaction_ms": 30},
}
NOISE_SD = {"heart_rate": 3, "hrv_rmssd": 6, "spo2": 0.6, "resp_rate": 1.0, "systolic_bp": 5,
            "diastolic_bp": 4, "core_temp": 0.12, "pvt_reaction_ms": 20}


@dataclass
class Episode:
    condition: str
    start_hour: int          # index into the hourly series
    duration_h: int
    intensity: float = 1.0   # ~0.35 (mild) .. 1.2 (severe)


@dataclass
class AstronautProfile:
    astronaut_id: str
    name: str
    role: str
    agency: str
    age: int
    sex: str                      # "F" / "M"
    mass_kg: float
    prior_career_dose_msv: float
    protein_g_per_kg: float
    vitamin_d_ng_ml: float
    ared_minutes_week: float      # planned resistive exercise
    aerobic_minutes_week: float
    baseline: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def random_profile(astronaut_id: str, rng: np.random.Generator) -> AstronautProfile:
    sex = rng.choice(["F", "M"])
    return AstronautProfile(
        astronaut_id=astronaut_id, name=astronaut_id, role="Crew", agency="SIM",
        age=int(rng.integers(32, 55)), sex=str(sex),
        mass_kg=float(rng.normal(64 if sex == "F" else 80, 7)),
        prior_career_dose_msv=float(rng.uniform(0, 250)),
        protein_g_per_kg=float(rng.uniform(0.9, 1.8)),
        vitamin_d_ng_ml=float(rng.uniform(18, 60)),
        ared_minutes_week=float(rng.uniform(150, 420)),
        aerobic_minutes_week=float(rng.uniform(120, 300)),
        baseline=dict(
            heart_rate=rng.normal(60, 5), hrv_rmssd=rng.normal(55, 10), spo2=rng.normal(97.8, 0.4),
            resp_rate=rng.normal(14, 1), systolic_bp=rng.normal(116, 6), diastolic_bp=rng.normal(74, 4),
            core_temp=rng.normal(36.85, 0.12), pvt_reaction_ms=rng.normal(255, 18),
            fluid_ml_per_awake_h=rng.normal(150, 15), co2_base=rng.normal(2.2, 0.25),
        ),
    )


def random_episodes(n_hours: int, rng: np.random.Generator, mean_gap_h: float = 80) -> list[Episode]:
    """Non-overlapping random episodes after the baseline period."""
    episodes, t = [], BASELINE_DAYS * 24 + 24
    kinds = CONDITIONS[1:]
    while True:
        t += int(rng.exponential(mean_gap_h)) + 12
        cond = str(rng.choice(kinds))
        if cond == "sleep_deprivation":
            t = (t // 24) * 24 + 6          # starts at wake-up after a short night
        dur = int(rng.integers(8, 30))
        if t + dur >= n_hours:
            break
        episodes.append(Episode(cond, t, dur, float(rng.uniform(0.35, 1.2))))
        t += dur
    return episodes


def simulate_astronaut(profile: AstronautProfile, days: int, rng: np.random.Generator,
                       episodes: list[Episode] | None = None,
                       radiation_msv_per_day: float = 1.0,
                       spe_events: list[tuple[int, int, float]] | None = None) -> pd.DataFrame:
    """Hourly telemetry for one astronaut.

    spe_events: list of (start_hour, duration_h, total_msv) solar particle events.
    """
    n = days * 24
    b = profile.baseline
    idx = np.arange(n)
    hour = idx % 24
    ts = MISSION_START + pd.to_timedelta(idx, unit="h")

    # --- schedule: sleep 22:00-06:00, resistive (ARED) ~09:00, aerobic ~15:00 ---------
    is_asleep = ((hour >= 22) | (hour < 6)).astype(float)
    activity = np.where(is_asleep == 1, 0.02, rng.uniform(0.12, 0.3, n))
    exercise_type = np.array(["none"] * n, dtype=object)
    ared_days_frac = min(profile.ared_minutes_week / 420, 1.0)
    aero_days_frac = min(profile.aerobic_minutes_week / 420, 1.0)
    for d in range(days):
        if rng.random() < ared_days_frac:
            h = d * 24 + 9 + int(rng.integers(0, 2))
            activity[h] = rng.uniform(0.6, 0.85); exercise_type[h] = "resistive"
        if rng.random() < aero_days_frac:
            h = d * 24 + 15 + int(rng.integers(0, 2))
            activity[h] = rng.uniform(0.55, 0.8); exercise_type[h] = "aerobic"

    circ = np.sin(2 * np.pi * (hour - 10) / 24)          # peaks mid-afternoon
    sig = {
        "heart_rate": b["heart_rate"] + 4 * circ - 7 * is_asleep + 70 * activity,
        "hrv_rmssd": b["hrv_rmssd"] + 12 * is_asleep - 25 * activity,
        "spo2": np.full(n, b["spo2"]) - 0.6 * activity,
        "resp_rate": b["resp_rate"] - 1.5 * is_asleep + 10 * activity,
        "systolic_bp": b["systolic_bp"] + 3 * circ - 8 * is_asleep + 25 * activity,
        "diastolic_bp": b["diastolic_bp"] + 2 * circ - 5 * is_asleep + 6 * activity,
        "core_temp": b["core_temp"] + 0.3 * circ + 0.6 * activity,
        "pvt_reaction_ms": b["pvt_reaction_ms"] + 10 * (hour < 9) * (1 - is_asleep),
    }
    fluid = np.where(is_asleep == 1, 0.0, b["fluid_ml_per_awake_h"] + 200 * activity)
    co2 = np.clip(b["co2_base"] + 0.35 * np.sin(2 * np.pi * idx / (24 * 5)), 1.0, None)
    rad = np.full(n, radiation_msv_per_day / 24.0)

    label = np.array(["nominal"] * n, dtype=object)
    for ep in episodes or []:
        s, e = ep.start_hour, min(ep.start_hour + ep.duration_h, n)
        L = ep.duration_h      # ramp over the full episode, then truncate at series end
        ramp = np.minimum(1, np.minimum(np.arange(1, L + 1) / 3, np.arange(L, 0, -1) / 3))[: e - s]
        r = ramp * ep.intensity
        for k, v in SIGNATURES[ep.condition].items():
            sig[k][s:e] += v * r
        label[s:e] = ep.condition
        if ep.condition == "sleep_deprivation":
            cut = int(round(2 + 3 * min(ep.intensity, 1.0)))      # 2..5 h of sleep lost
            night = np.arange(max(s - 8, 0), max(s - 8, 0) + cut)
            is_asleep[night] = 0; activity[night] = 0.15
            fluid[night] = b["fluid_ml_per_awake_h"] * 0.5
        elif ep.condition == "dehydration":
            fluid[s:e] *= np.clip(1 - 0.8 * r, 0.15, 1)
            pre = slice(max(s - 6, 0), s)                       # intake already dropping
            fluid[pre] *= 0.5
        elif ep.condition == "co2_exposure":
            co2[s:e] += (2.5 + 3.5 * ep.intensity) * ramp
        elif ep.condition == "hypoxia":
            pass

    for sp in spe_events or []:
        s, dur, total = sp
        rad[s:s + dur] += total / dur

    df = pd.DataFrame({"timestamp": ts, "astronaut_id": profile.astronaut_id,
                       "mission_day": idx // 24 + 1, "hour": hour})
    for k, v in sig.items():
        df[k] = v + rng.normal(0, NOISE_SD[k], n)
    df["spo2"] = df["spo2"].clip(upper=100)
    df["pvt_reaction_ms"] = df["pvt_reaction_ms"].where(is_asleep == 0).ffill().bfill()
    df["activity_level"] = activity.round(3)
    df["is_asleep"] = is_asleep.astype(int)
    df["exercise_type"] = exercise_type
    df["fluid_intake_ml"] = np.clip(fluid + rng.normal(0, 25, n) * (is_asleep == 0), 0, None)
    df["cabin_co2_mmhg"] = np.clip(co2 + rng.normal(0, 0.2, n), 0.5, None)
    df["radiation_msv"] = rad * rng.lognormal(0, 0.15, n)
    df["label"] = label
    num = df.select_dtypes("number").columns
    df[num] = df[num].round(3)
    return df


# ---------------------------------------------------------------------------
# Long-term deconditioning (bone + muscle) cohort
# ---------------------------------------------------------------------------
def true_bmd_rate(ared, aerobic, protein, vitd, age, sex, rng=None):
    """Hip areal BMD loss, % per month. ~1-1.5 %/mo without countermeasures
    (Mir/ISS DXA literature); reduced by resistive exercise, nutrition."""
    rate = 1.55 * (1 - 0.55 * np.minimum(ared / 360, 1.2)) \
        - 0.08 * np.minimum(aerobic / 240, 1.5) \
        + 0.18 * (vitd < 30) - 0.12 * (protein - 1.2) \
        + 0.10 * (sex == "F") + 0.008 * (age - 42)
    if rng is not None:
        rate = rate + rng.normal(0, 0.12, np.shape(rate))
    return np.clip(rate, 0.05, None)


def true_muscle_rate(ared, aerobic, protein, age, rng=None):
    """Thigh muscle volume loss, % per month."""
    rate = 2.4 * (1 - 0.6 * np.minimum(ared / 360, 1.2)) - 0.1 * np.minimum(aerobic / 240, 1.5) \
        - 0.35 * (protein - 1.2) + 0.012 * (age - 42)
    if rng is not None:
        rate = rate + rng.normal(0, 0.18, np.shape(rate))
    return np.clip(rate, 0.05, None)


def simulate_deconditioning_cohort(n_missions: int, rng: np.random.Generator) -> pd.DataFrame:
    """One row per astronaut-month: inputs over the last 4 weeks -> observed monthly loss."""
    rows = []
    for m in range(n_missions):
        p = random_profile(f"SIM-{m:04d}", rng)
        months = int(rng.integers(2, 8))
        adherence = rng.uniform(0.5, 1.1)
        for mo in range(1, months + 1):
            ared = np.clip(p.ared_minutes_week * adherence * rng.uniform(0.8, 1.15), 0, 600)
            aero = np.clip(p.aerobic_minutes_week * rng.uniform(0.75, 1.15), 0, 500)
            prot = np.clip(p.protein_g_per_kg + rng.normal(0, 0.1), 0.6, 2.2)
            rows.append(dict(
                mission_id=p.astronaut_id, mission_month=mo, age=p.age, sex=p.sex,
                ared_minutes_week=round(ared, 1), aerobic_minutes_week=round(aero, 1),
                protein_g_per_kg=round(prot, 2), vitamin_d_ng_ml=round(p.vitamin_d_ng_ml, 1),
                bmd_loss_pct_month=float(true_bmd_rate(ared, aero, prot, p.vitamin_d_ng_ml,
                                                      p.age, p.sex, rng)),
                muscle_loss_pct_month=float(true_muscle_rate(ared, aero, prot, p.age, rng)),
            ))
    return pd.DataFrame(rows).round(3)


# ---------------------------------------------------------------------------
# Demo crew for the app (fictional people, scripted current situations)
# ---------------------------------------------------------------------------
DEMO_MISSION = {
    "mission_id": "SOL-1",
    "name": "Sol-1 (fictional long-duration lunar Gateway mission)",
    "vehicle": "Gateway habitat (simulated)",
    "start": str(MISSION_START.date()),
    "planned_duration_days": 180,
    "current_day": 75,
    "radiation_msv_per_day_assumed": 1.0,
    "earth_comm_delay_s": 1.3,
    "note": "All crew and telemetry are synthetic. Generated by ml/sol_ml/simulate.py.",
}

DEMO_CREW = [
    dict(astronaut_id="UH-01", name="Nadia Farouk", role="Commander", agency="Fictional",
         age=46, sex="F", mass_kg=63.0, prior_career_dose_msv=180.0, protein_g_per_kg=1.5,
         vitamin_d_ng_ml=42.0, ared_minutes_week=380, aerobic_minutes_week=260),
    dict(astronaut_id="UH-02", name="Karim Adel", role="Flight Engineer", agency="Fictional",
         age=39, sex="M", mass_kg=81.0, prior_career_dose_msv=60.0, protein_g_per_kg=1.2,
         vitamin_d_ng_ml=33.0, ared_minutes_week=300, aerobic_minutes_week=220),
    dict(astronaut_id="UH-03", name="Sofia Mendes", role="Mission Specialist", agency="Fictional",
         age=35, sex="F", mass_kg=58.0, prior_career_dose_msv=0.0, protein_g_per_kg=1.0,
         vitamin_d_ng_ml=24.0, ared_minutes_week=210, aerobic_minutes_week=180),
    dict(astronaut_id="UH-04", name="Yuki Tanaka", role="Crew Medical Officer", agency="Fictional",
         age=51, sex="M", mass_kg=74.0, prior_career_dose_msv=240.0, protein_g_per_kg=1.4,
         vitamin_d_ng_ml=38.0, ared_minutes_week=340, aerobic_minutes_week=240),
]


def build_demo(seed: int = 7) -> dict:
    rng = np.random.default_rng(seed)
    days = DEMO_MISSION["current_day"]
    n = days * 24
    now = n - 1
    # scripted episodes: (past events) + (what is happening right now)
    scripts = {
        "UH-01": [Episode("sleep_deprivation", 49 * 24 + 6, 20, 0.8),
                  Episode("co2_exposure", 61 * 24 + 1, 10, 0.7)],
        "UH-02": [Episode("cardiovascular_strain", 40 * 24 + 10, 6, 0.6),
                  Episode("dehydration", now - 6, 12, 0.6)],
        "UH-03": [Episode("sleep_deprivation", 66 * 24 + 6, 18, 1.0),
                  Episode("co2_exposure", now - 7, 10, 1.1)],
        "UH-04": [Episode("dehydration", 30 * 24 + 12, 14, 0.7),
                  Episode("fever_infection", now - 5, 10, 0.75)],
    }
    spe = [(58 * 24 + 4, 10, 12.0)]       # a modest solar particle event on day 59
    frames, crew = [], []
    for c in DEMO_CREW:
        p = random_profile(c["astronaut_id"], rng)
        for k, v in c.items():
            setattr(p, k, v)
        df = simulate_astronaut(p, days, rng, scripts[c["astronaut_id"]],
                                DEMO_MISSION["radiation_msv_per_day_assumed"], spe)
        frames.append(df)
        prof = p.to_dict()
        # personal baseline = calibration over the first mission days (same as training)
        from .features import compute_baseline
        prof["baseline"] = {k: round(v, 2) for k, v in compute_baseline(df).items()}
        crew.append(prof)
    telemetry = pd.concat(frames, ignore_index=True)
    return {"mission": DEMO_MISSION, "crew": crew, "telemetry": telemetry}


def write_demo(seed: int = 7) -> None:
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    demo = build_demo(seed)
    tel = demo["telemetry"]
    # the scripted label is ground truth for the simulation only; keep it in a separate column
    tel = tel.rename(columns={"label": "sim_ground_truth"})
    tel.to_csv(DEMO_DIR / "telemetry.csv", index=False)
    with open(DEMO_DIR / "crew.json", "w") as f:
        json.dump({"mission": demo["mission"], "crew": demo["crew"]}, f, indent=2)
    print(f"demo: {len(tel)} rows, {len(demo['crew'])} crew -> {DEMO_DIR}")


if __name__ == "__main__":
    write_demo()
