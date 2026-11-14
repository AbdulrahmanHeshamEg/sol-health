"""Data-calibrated demo astronaut (notebook 08): real datasets set the statistics, the astronaut is SIMULATED.

One astronaut on a solo mission carries all four planted test cases, at different times, so a single personal
app shows every case. (The module is still called `crew` and the files `crew.json` for continuity with v0.)

    from sol_ml.sim import crew
    demo = crew.build_demo(seed=42)      # dict: mission, crew, telemetry, daily, planted_cases, sources
    crew.write_demo(demo)                # -> data/demo/

What comes from where (also written to data/demo/sources.json and shown in the app):
  resting HR, sleep, fatigue / mood / stress  simulated, statistics fitted to PMData (real people on Earth)
  hourly heart-rate shape and noise           simulated, fitted to PMData
  cabin CO2                                   simulated, block bootstrap of real ISS CO2 (OSDR EDA)
  radiation dose rate                         REAL MSL RAD measurements replayed (Mars surface, incl. the May 2024 storm)
  BP, SpO2, temperature, respiration, HRV,
  reaction time, fluids, blood glucose        simulated from published normal ranges (in no real dataset)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import DATA_DIR, DEMO_DIR
from ..detectors.radiation import QUALITY_FACTOR
from . import co2 as co2_sim
from .. import simulate as v0

PROCESSED = DATA_DIR / "processed"
REPORTS = ["fatigue", "mood", "stress"]          # PMSys scale: 1 = worst, 3 = normal, 5 = best
LEVELS = np.arange(1, 6)
WAKE_HOUR = 6
STORM_ONSET = pd.Timestamp("2024-05-20 05:00:00")
BASE_CO2_MISSION, HIGH_CO2_MISSION = "RR-23", "RR-1"   # recent quiet cabin; an early mission that sat just over the 7-day limit
# The one astronaut of the solo mission (fictional). Exercise plan and nutrition follow the v0 profile format.
SOLO_ASTRONAUT = dict(astronaut_id="UH-01", name="Nadia Farouk", role="Mission astronaut", agency="Fictional",
                      age=46, sex="F", mass_kg=63.0, prior_career_dose_msv=180.0, protein_g_per_kg=1.5,
                      vitamin_d_ng_ml=42.0, ared_minutes_week=380, aerobic_minutes_week=260)
EXCLUDED_PEOPLE = ("p12", "p13")                  # almost no Fitbit data (notebook 01)

MISSION = {
    "mission_id": "SOL-1",
    "name": "Sol-1 (fictional solo Mars surface mission)",
    "vehicle": "Mars surface habitat (simulated)",
    "setting": "mars_surface",
    "start": "2026-08-31",
    "planned_duration_days": 500,
    "current_day": 75,
    "radiation_msv_per_day_assumed": 0.49,
    "earth_comm_delay_s": 780,
    "crew_size": 1,
    "note": "The astronaut is fictional and simulated. Statistics are calibrated on real data: PMData (body), "
            "NASA OSDR EDA (cabin CO2) and NASA/JPL MSL RAD (radiation, replayed real measurements).",
}

SOURCES = {
    "resting_hr": {"kind": "simulated", "calibrated_on": "PMData"},
    "sleep_minutes": {"kind": "simulated", "calibrated_on": "PMData"},
    "fatigue": {"kind": "simulated", "calibrated_on": "PMData"},
    "mood": {"kind": "simulated", "calibrated_on": "PMData"},
    "stress": {"kind": "simulated", "calibrated_on": "PMData"},
    "heart_rate": {"kind": "simulated", "calibrated_on": "PMData"},
    "cabin_co2_mmhg": {"kind": "simulated", "calibrated_on": "NASA OSDR EDA (ISS cabin)"},
    "radiation_ugy_per_day": {"kind": "real", "dataset": "NASA/JPL MSL RAD (Curiosity), replayed"},
    "radiation_msv": {"kind": "real", "dataset": "NASA/JPL MSL RAD x quality factor 3.0, replayed"},
    "systolic_bp": {"kind": "simulated", "calibrated_on": "published normal ranges"},
    "diastolic_bp": {"kind": "simulated", "calibrated_on": "published normal ranges"},
    "spo2": {"kind": "simulated", "calibrated_on": "published normal ranges"},
    "core_temp": {"kind": "simulated", "calibrated_on": "published normal ranges"},
    "resp_rate": {"kind": "simulated", "calibrated_on": "published normal ranges"},
    "hrv_rmssd": {"kind": "simulated", "calibrated_on": "published normal ranges"},
    "pvt_reaction_ms": {"kind": "simulated", "calibrated_on": "published normal ranges"},
    "fluid_intake_ml": {"kind": "simulated", "calibrated_on": "published normal ranges"},
    "blood_glucose_mg_dl": {"kind": "simulated", "calibrated_on": "published normal ranges"},
    "headache": {"kind": "simulated", "calibrated_on": "scripted for the planted cabin case"},
    "urine_sg": {"kind": "simulated", "calibrated_on": "published normal ranges (urine dipstick)"},
    "urine_ph": {"kind": "simulated", "calibrated_on": "published normal ranges (urine dipstick)"},
    "urine_blood": {"kind": "simulated", "calibrated_on": "published normal ranges (urine dipstick)"},
    "urine_protein": {"kind": "simulated", "calibrated_on": "published normal ranges (urine dipstick)"},
    "urine_glucose": {"kind": "simulated", "calibrated_on": "published normal ranges (urine dipstick)"},
    "urine_ketones": {"kind": "simulated", "calibrated_on": "published normal ranges (urine dipstick)"},
    "urine_leukocytes": {"kind": "simulated", "calibrated_on": "published normal ranges (urine dipstick)"},
    "urine_nitrite": {"kind": "simulated", "calibrated_on": "published normal ranges (urine dipstick)"},
    "stool_bristol": {"kind": "simulated", "calibrated_on": "published Bristol stool scale distribution"},
    "stool_count": {"kind": "simulated", "calibrated_on": "published normal ranges"},
    "stool_blood": {"kind": "simulated", "calibrated_on": "published normal ranges"},
    "fundus_photo": {"kind": "simulated", "calibrated_on": "synthetic retina image (sol_ml.sim.fundus_image)"},
}


# --------------------------------------------------------------------------- calibration on PMData
def transition_matrix(values: np.ndarray, smoothing: float = 0.1) -> np.ndarray:
    """5x5 day-to-day transition probabilities of a 1-5 report (rows = today, columns = tomorrow)."""
    v = np.asarray(values, float)
    counts = np.full((5, 5), smoothing)
    for a, b in zip(v[:-1], v[1:]):
        if not (np.isnan(a) or np.isnan(b)):
            counts[int(a) - 1, int(b) - 1] += 1
    return counts / counts.sum(axis=1, keepdims=True)


def fit_body_params(daily: pd.DataFrame, hourly: pd.DataFrame | None = None) -> dict:
    """Statistics of the real PMData people that the generator reproduces."""
    daily = daily[~daily["person"].isin(EXCLUDED_PEOPLE)]
    groups = [g.sort_values("date") for _, g in daily.groupby("person")]
    hr = [g["resting_hr"] for g in groups if g["resting_hr"].notna().sum() >= 60]
    sleep = [g["sleep_minutes"].dropna() for g in groups if g["sleep_minutes"].notna().sum() >= 60]
    params = {
        "resting_hr": {"mean": float(np.mean([s.median() for s in hr])), "between_sd": float(np.std([s.median() for s in hr], ddof=1)),
                       "within_sd": float(np.median([s.std() for s in hr])),
                       "phi": float(np.median([s.autocorr(1) for s in hr]))},
        "sleep_minutes": {"mean": float(np.mean([s.median() for s in sleep])), "between_sd": float(np.std([s.median() for s in sleep], ddof=1)),
                          "within_sd": float(np.median([s.std() for s in sleep])),
                          "residuals": np.concatenate([((s - s.median()) / s.std()).to_numpy() for s in sleep])},
        "reports": {r: [transition_matrix(g[r].to_numpy()) for g in groups if g[r].notna().sum() >= 60] for r in REPORTS},
    }
    if hourly is not None:
        hourly = hourly[~hourly["person"].isin(EXCLUDED_PEOPLE)].copy()
        rest = daily.groupby("person")["resting_hr"].median()
        hourly["rel"] = hourly["hr_mean"] - hourly["person"].map(rest)
        hourly["hod"] = hourly["hour"].dt.hour
        by_person = hourly.groupby(["person", "hod"])["rel"].mean().unstack(0)
        night = hourly[hourly["hod"].between(1, 4)]
        resid = night["rel"] - night.groupby(["person", "hod"])["rel"].transform("mean")
        params["hr_profile"] = by_person.mean(axis=1).to_numpy()
        params["hr_noise_sd"] = float(resid.groupby(night["person"]).std().median())
    return params


# --------------------------------------------------------------------------- daily body signals
def gen_resting_hr(p: dict, days: int, rng: np.random.Generator, mean: float | None = None) -> np.ndarray:
    """AR(1) around a personal mean: same day-to-day memory and spread as real resting HR."""
    mean = rng.normal(p["mean"], p["between_sd"]) if mean is None else mean
    shock_sd = p["within_sd"] * np.sqrt(1 - p["phi"] ** 2)
    out, state = np.empty(days), rng.normal(0, p["within_sd"])
    for t in range(days):
        state = p["phi"] * state + rng.normal(0, shock_sd)
        out[t] = mean + state
    return out


def gen_sleep_minutes(p: dict, days: int, rng: np.random.Generator, mean: float | None = None) -> np.ndarray:
    """Personal mean plus resampled real night-to-night residuals (keeps the real skew and the occasional short night)."""
    mean = rng.normal(p["mean"], p["between_sd"]) if mean is None else mean
    return np.clip(mean + p["within_sd"] * rng.choice(p["residuals"], days), 180, 600)


def gen_report(matrix: np.ndarray, days: int, rng: np.random.Generator) -> np.ndarray:
    """A 1-5 self-report as a Markov chain with a real person's day-to-day transition matrix."""
    stationary = np.linalg.matrix_power(matrix, 50)[0]
    out = np.empty(days)
    state = rng.choice(5, p=stationary)
    for t in range(days):
        state = rng.choice(5, p=matrix[state])
        out[t] = state + 1
    return out


def gen_daily(params: dict, days: int, rng: np.random.Generator) -> pd.DataFrame:
    """One simulated crewmember's daily body table (no planted cases yet)."""
    df = pd.DataFrame({"mission_day": np.arange(1, days + 1),
                       "resting_hr": gen_resting_hr(params["resting_hr"], days, rng).round(1),
                       "sleep_minutes": gen_sleep_minutes(params["sleep_minutes"], days, rng).round(0)})
    for r in REPORTS:
        donors = params["reports"][r]
        df[r] = gen_report(donors[rng.integers(len(donors))], days, rng)
    df["headache"] = 0
    df["blood_glucose_mg_dl"] = np.clip(rng.normal(rng.normal(90, 4), 6, days), 65, 125).round(0)      # fasting, published range
    # urine dipstick (published normal ranges; pads read 0 = negative, 1 = trace, 2 = +, 3 = ++)
    df["urine_sg"] = np.clip(rng.normal(1.017, 0.004, days), 1.003, 1.029).round(3)
    df["urine_ph"] = np.clip(rng.normal(6.2, 0.5, days), 4.5, 8.0).round(1)
    for pad, p_trace in (("urine_blood", 0.01), ("urine_protein", 0.03), ("urine_glucose", 0.0), ("urine_ketones", 0.03),
                         ("urine_leukocytes", 0.02)):
        df[pad] = (rng.random(days) < p_trace).astype(int)
    df["urine_nitrite"] = 0
    # stool: Bristol type 1-7 (3-5 = normal), motions per day, visible blood
    df["stool_bristol"] = rng.choice(np.arange(1, 8), size=days, p=[0.01, 0.05, 0.24, 0.42, 0.19, 0.08, 0.01])
    df["stool_count"] = np.clip(rng.poisson(1.1, days), 0, 3)
    df["stool_blood"] = 0
    df["flank_pain"] = 0
    df["vision_change"] = 0
    return df


# --------------------------------------------------------------------------- planted cases
def plant_slow_drift(daily: pd.DataFrame, start_day: int, days: int = 10, hr_bpm: float = 6.0,
                     sleep_min: float = 60.0, fatigue_points: float = 1.0, rng=None, until_day: int | None = None) -> pd.DataFrame:
    """Case 1 (illness onset): resting HR up, sleep down and fatigue worse, ramping over `days`, then held
    until `until_day` (the illness resolves the next day; None = held to the end)."""
    out = daily.copy()
    sel = out["mission_day"] >= start_day
    if until_day is not None:
        sel &= out["mission_day"] <= until_day
    ramp = np.minimum((out.loc[sel, "mission_day"] - start_day + 1) / days, 1.0)
    out.loc[sel, "resting_hr"] = (out.loc[sel, "resting_hr"] + hr_bpm * ramp).round(1)
    out.loc[sel, "sleep_minutes"] = (out.loc[sel, "sleep_minutes"] - sleep_min * ramp).clip(lower=180).round(0)
    drop = fatigue_points * ramp
    whole = np.floor(drop) + ((rng or np.random.default_rng(0)).random(len(drop)) < (drop - np.floor(drop)))
    out.loc[sel, "fatigue"] = (out.loc[sel, "fatigue"] - whole).clip(lower=1)
    return out


def plant_odd_combination(daily: pd.DataFrame, start_day: int, days: int = 7, sleep_min: float = 55.0) -> pd.DataFrame:
    """Case 2 (behavioural health): mood and stress one point worse and sleep a little shorter, together.
    Each change alone stays inside the person's normal range."""
    out = daily.copy()
    sel = out["mission_day"].between(start_day, start_day + days - 1)
    for r in ("mood", "stress"):
        out.loc[sel, r] = (out.loc[sel, r] - 1).clip(lower=1)
    out.loc[sel, "sleep_minutes"] = (out.loc[sel, "sleep_minutes"] - sleep_min).clip(lower=180)
    return out


def plant_symptoms(daily: pd.DataFrame, start_day: int, days: int) -> pd.DataFrame:
    """Case 3 (cabin CO2): daily headache reports and a fatigue score no better than 2 while CO2 is high."""
    out = daily.copy()
    sel = out["mission_day"].between(start_day, start_day + days - 1)
    out.loc[sel, "headache"] = 1
    out.loc[sel, "fatigue"] = out.loc[sel, "fatigue"].clip(upper=2)
    return out


# --------------------------------------------------------------------------- cabin and radiation
def splice(base: np.ndarray, segment: np.ndarray, start: int, fade: int = 12) -> np.ndarray:
    """Replace base[start : start+len(segment)] by `segment`, cross-fading over `fade` hours at both ends."""
    out = np.array(base, float)
    n = min(len(segment), len(out) - start)
    weight = np.minimum(1.0, np.minimum(np.arange(1, n + 1), np.arange(n, 0, -1)) / fade)
    out[start: start + n] = weight * segment[:n] + (1 - weight) * out[start: start + n]
    return out


def highest_stretch(real: np.ndarray, hours: int) -> np.ndarray:
    """The contiguous `hours`-long piece of a real series with the highest mean (gaps filled by interpolation)."""
    s = pd.Series(real).interpolate(limit=12).dropna().to_numpy()
    means = pd.Series(s).rolling(hours).mean().to_numpy()
    end = int(np.nanargmax(means)) + 1
    return s[end - hours: end]


def cabin_co2(base_real: np.ndarray, high_real: np.ndarray, n_hours: int, rng: np.random.Generator,
              high_start: int | None = None, high_hours: int = 240) -> np.ndarray:
    """Cabin CO2 (mmHg): block bootstrap of a recent real ISS mission, optionally with a real high-CO2 stretch
    of an older mission spliced in (the planted cabin case)."""
    co2 = co2_sim.block_bootstrap(pd.Series(base_real).interpolate(limit=12).to_numpy(), n_hours, rng)
    if high_start is not None:
        co2 = splice(co2, highest_stretch(high_real, high_hours), high_start)
    return co2


def radiation_replay(rad_hourly: pd.DataFrame, n_hours: int, storm_hour: int) -> pd.Series:
    """Real MSL RAD hourly dose rate (uGy/day), cut so that the May 2024 storm onset lands on mission hour `storm_hour`.
    Hours without data take the median of the previous day. The index holds the original RAD timestamps."""
    s = rad_hourly.set_index("hour")["dose_e"]
    first = STORM_ONSET - pd.Timedelta(hours=storm_hour)
    window = s.loc[first: first + pd.Timedelta(hours=n_hours - 1)]
    return window.fillna(window.rolling(24, min_periods=1).median()).ffill().bfill()


# --------------------------------------------------------------------------- hourly telemetry
def asleep_mask(sleep_minutes: np.ndarray) -> np.ndarray:
    """Hourly 0/1 sleep flags: each night's sleep ends at 06:00 and lasts round(minutes / 60) hours."""
    days = len(sleep_minutes)
    mask = np.zeros(days * 24, int)
    for d, minutes in enumerate(sleep_minutes):
        wake = d * 24 + WAKE_HOUR
        mask[max(wake - int(round(minutes / 60)), 0): wake] = 1
    return mask


def build_hourly(profile: v0.AstronautProfile, daily: pd.DataFrame, co2: np.ndarray, rad_ugy: np.ndarray,
                 params: dict, rng: np.random.Generator) -> pd.DataFrame:
    """Hourly telemetry in the v0 column layout. Vitals that exist in no real dataset come from the v0 simulator
    (published normal ranges); heart rate, sleep, CO2 and radiation are replaced by the calibrated series."""
    days = len(daily)
    df = v0.simulate_astronaut(profile, days, rng).drop(columns=["label"])
    hour = df["hour"].to_numpy()
    asleep = asleep_mask(daily["sleep_minutes"].to_numpy())
    exercising = df["exercise_type"].ne("none").to_numpy()
    asleep[exercising] = 0
    resting = np.repeat(daily["resting_hr"].to_numpy(), 24)
    noise = rng.normal(0, params["hr_noise_sd"], len(df))
    # awake, non-exercise hours: the hour-to-hour scatter of heart rate IS activity (moving about vs sitting still)
    moving = np.clip(0.2 + noise / 60.0, 0.05, 0.45)
    activity = np.where(asleep == 1, 0.02, np.where(exercising, df["activity_level"], moving))
    df["heart_rate"] = (resting + params["hr_profile"][hour] + 70 * np.where(exercising, activity, 0) + noise).round(1)
    df["is_asleep"], df["activity_level"] = asleep, np.round(activity, 3)
    df.loc[asleep == 1, "fluid_intake_ml"] = 0.0
    df["cabin_co2_mmhg"] = np.round(np.clip(co2 + rng.normal(0, 0.03, len(df)), 0.3, None), 3)
    df["radiation_ugy_per_day"] = np.round(rad_ugy, 1)
    df["radiation_msv"] = np.round(rad_ugy * QUALITY_FACTOR / 1000.0 / 24.0, 5)
    return df


# --------------------------------------------------------------------------- the demo crew
def build_demo(seed: int = 42, processed: Path = PROCESSED) -> dict:
    rng = np.random.default_rng(seed)
    pm_daily = pd.read_parquet(processed / "pmdata_daily.parquet")
    pm_hourly = pd.read_parquet(processed / "pmdata_hourly_hr.parquet")
    cabin = pd.read_parquet(processed / "iss_cabin.parquet")
    rad = pd.read_parquet(processed / "msl_rad_hourly.parquet")
    params = fit_body_params(pm_daily, pm_hourly)

    days = MISSION["current_day"]
    n = days * 24
    start = pd.Timestamp(MISSION["start"])
    me = SOLO_ASTRONAUT["astronaut_id"]
    # all four cases on the one astronaut, never overlapping; the storm is under way "now"
    plan = {"co2": dict(start_day=24, days=10, who=me), "drift": dict(start_day=40, days=10, until=54, who=me),
            "combo": dict(start_day=62, days=7, who=me), "storm": dict(day=days),
            "eyes": dict(exams=[(1, 11, 0.0), (30, 12, 0.0), (60, 15, 0.25)], case_day=60, who=me)}   # (day, image seed, swelling)

    base_real = cabin.loc[cabin["mission"] == BASE_CO2_MISSION, "co2_mmhg"].to_numpy()
    high_real = cabin.loc[cabin["mission"] == HIGH_CO2_MISSION, "co2_mmhg"].to_numpy()
    co2 = cabin_co2(base_real, high_real, n, rng, high_start=(plan["co2"]["start_day"] - 1) * 24,
                    high_hours=plan["co2"]["days"] * 24)
    storm_hour = (plan["storm"]["day"] - 1) * 24 + STORM_ONSET.hour
    replay = radiation_replay(rad, n, storm_hour)

    frames, dailies, crew = [], [], []
    for c in [SOLO_ASTRONAUT]:
        profile = v0.random_profile(c["astronaut_id"], rng)
        for k, v in c.items():
            setattr(profile, k, v)
        daily = gen_daily(params, days, rng)
        if c["astronaut_id"] == plan["co2"]["who"]:
            daily = plant_symptoms(daily, plan["co2"]["start_day"] + 3, plan["co2"]["days"] - 3)
        if c["astronaut_id"] == plan["drift"]["who"]:
            daily = plant_slow_drift(daily, plan["drift"]["start_day"], plan["drift"]["days"], rng=rng, until_day=plan["drift"]["until"])
        if c["astronaut_id"] == plan["combo"]["who"]:
            daily = plant_odd_combination(daily, plan["combo"]["start_day"], plan["combo"]["days"])
        hourly = build_hourly(profile, daily, co2, replay.to_numpy(), params, rng)
        frames.append(hourly)
        daily.insert(0, "date", (start + pd.to_timedelta(daily["mission_day"] - 1, unit="D")).dt.strftime("%Y-%m-%d"))
        daily.insert(0, "astronaut_id", c["astronaut_id"])
        dailies.append(daily)
        from ..features import compute_baseline
        prof = profile.to_dict()
        prof["baseline"] = {k: round(v, 2) for k, v in compute_baseline(hourly).items()}
        crew.append(prof)

    def ts(day: int, hour: int = 0) -> str:
        return str(start + pd.Timedelta(days=day - 1, hours=hour))

    p = plan
    cases = [
        {"id": "cabin_co2", "title": "Cabin CO2 with headache reports", "astronaut_id": p["co2"]["who"], "affects": "the habitat cabin and you",
         "start": ts(p["co2"]["start_day"]), "end": ts(p["co2"]["start_day"] + p["co2"]["days"]),
         "planted": "the highest real 10-day CO2 stretch of ISS mission %s spliced into the cabin series; daily headache reports and fatigue <= 2 from day %d"
                    % (HIGH_CO2_MISSION, p["co2"]["start_day"] + 3),
         "expected": "environmental gate: 7-day CO2 mean above 2.5 mmHg with symptoms -> 'likely environmental', ventilation first"},
        {"id": "slow_drift", "title": "Slow drift (illness onset)", "astronaut_id": p["drift"]["who"], "affects": "you",
         "start": ts(p["drift"]["start_day"]), "end": ts(p["drift"]["until"], 23),
         "planted": "resting HR +6 bpm, sleep -60 min and fatigue one point worse, ramping over 10 days, held until day %d, then resolved"
                    % p["drift"]["until"],
         "expected": "CUSUM on the personal z-score of resting HR / sleep / fatigue"},
        {"id": "solar_storm", "title": "Solar storm (SPE)", "astronaut_id": me, "affects": "the habitat and you",
         "start": ts(p["storm"]["day"], STORM_ONSET.hour), "end": ts(days, 23),
         "planted": "replay of the real 20 May 2024 storm measured by MSL RAD (nothing was scaled)",
         "expected": "SPE alarm in the first hour: radiation elevated (>= 1.3x) then go to the storm shelter (>= 2x); flight surgeon notified"},
        {"id": "optic_disc", "title": "Eye exam: optic disc swelling (SANS)", "astronaut_id": me, "affects": "you",
         "start": ts(p["eyes"]["case_day"], 9), "end": ts(days, 23),
         "planted": "the day-60 fundus photo (synthetic) shows an early swollen optic disc: blurred margin, slightly larger disc; days 1 and 30 are normal",
         "expected": "fundus photo check: margin less sharp than the baseline photo -> watch alert, photo sent to the flight surgeon"},
        {"id": "odd_combination", "title": "Odd combination (behavioural health)", "astronaut_id": p["combo"]["who"], "affects": "you",
         "start": ts(p["combo"]["start_day"]), "end": ts(p["combo"]["start_day"] + p["combo"]["days"]),
         "planted": "mood and stress one point worse and sleep 55 min shorter for 7 days; each within the normal range alone",
         "expected": "multivariate model (Isolation Forest on the daily z-vector)"},
    ]
    mission = dict(MISSION, radiation_replay={"dataset": "MSL RAD", "from": str(replay.index[0]), "to": str(replay.index[-1])},
                   cabin_co2_source={"base": BASE_CO2_MISSION + " (2020)", "planted_high": HIGH_CO2_MISSION + " (2014)"})
    from . import fundus_image
    eye_exams = [{"date": ts(day, 9), "mission_day": day, "image": f"eye_day{day:02d}.png",
                  "png": fundus_image.render(seed=seed, swelling=swelling)} for day, seed, swelling in p["eyes"]["exams"]]
    return {"mission": mission, "crew": crew, "eye_exams": eye_exams, "telemetry": pd.concat(frames, ignore_index=True),
            "daily": pd.concat(dailies, ignore_index=True), "planted_cases": cases, "sources": SOURCES, "params": params}


def write_demo(demo: dict, out_dir: Path = DEMO_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    demo["telemetry"].to_csv(out_dir / "telemetry.csv", index=False)
    demo["daily"].to_csv(out_dir / "daily.csv", index=False)
    (out_dir / "crew.json").write_text(json.dumps({"mission": demo["mission"], "crew": demo["crew"]}, indent=2))
    (out_dir / "planted_cases.json").write_text(json.dumps(demo["planted_cases"], indent=2))
    (out_dir / "sources.json").write_text(json.dumps(demo["sources"], indent=2))
    eyes = out_dir / "eye_exams"
    eyes.mkdir(exist_ok=True)
    for exam in demo.get("eye_exams", []):
        (eyes / exam["image"]).write_bytes(exam["png"])
    (out_dir / "eye_exams.json").write_text(json.dumps([{k: v for k, v in e.items() if k != "png"} for e in demo.get("eye_exams", [])], indent=2))
