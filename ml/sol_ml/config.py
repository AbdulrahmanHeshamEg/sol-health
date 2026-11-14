"""Shared constants: signals, conditions, clinical thresholds, mission limits.

Every threshold here is referenced in docs/CLINICAL_PROTOCOLS.md. Keep the two in sync.
Values are for a hackathon demo of decision support, not for clinical use.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT / "models"
DATA_DIR = ROOT / "data"
DEMO_DIR = DATA_DIR / "demo"
DEMO_V0_DIR = DATA_DIR / "demo_v0"          # the purely simulated v0 crew, kept as the baseline

# ---------------------------------------------------------------------------
# Hourly telemetry signals (one row = one astronaut-hour)
# ---------------------------------------------------------------------------
VITAL_SIGNALS = [
    "heart_rate",        # bpm
    "hrv_rmssd",         # ms
    "spo2",              # %
    "resp_rate",         # breaths/min
    "systolic_bp",       # mmHg
    "diastolic_bp",      # mmHg
    "core_temp",         # deg C
    "pvt_reaction_ms",   # psychomotor vigilance reaction time, ms
]
CONTEXT_SIGNALS = [
    "activity_level",    # 0..1 (0 rest, 1 max exercise)
    "is_asleep",         # 0/1
    "fluid_intake_ml",   # ml in this hour
    "cabin_co2_mmhg",    # local ppCO2 at crew location
    "radiation_msv",     # effective dose received in this hour, mSv
]
ALL_SIGNALS = VITAL_SIGNALS + CONTEXT_SIGNALS

# ---------------------------------------------------------------------------
# Conditions the risk classifier predicts
# ---------------------------------------------------------------------------
CONDITIONS = [
    "nominal",
    "sleep_deprivation",
    "dehydration",
    "co2_exposure",
    "cardiovascular_strain",
    "fever_infection",
    "hypoxia",
]
CONDITION_LABELS = {
    "nominal": "Nominal",
    "sleep_deprivation": "Fatigue / sleep debt",
    "dehydration": "Dehydration",
    "co2_exposure": "Elevated CO2 exposure",
    "cardiovascular_strain": "Cardiovascular strain",
    "fever_infection": "Fever / possible infection",
    "hypoxia": "Low blood oxygen (hypoxia)",
}

# ---------------------------------------------------------------------------
# Conditions of the v2 engine (sol_ml.engine). The list above belongs to the v0 classifier baseline.
# ---------------------------------------------------------------------------
ENGINE_CONDITION_LABELS = {
    "nominal": "Nominal",
    "acute_deviation": "Unusual reading for you",
    "physiological_drift": "Slow drift from your normal",
    "unusual_combination": "Unusual combination of signals",
    "low_mood": "Low mood for several days",
    "deconditioning": "Fitness may be slipping",
    "co2_exposure": "Elevated CO2 / likely environmental",
    "radiation_event": "Solar particle event",
    "hypoxia": "Low blood oxygen (hypoxia)",
    "fever_infection": "Fever / possible infection",
    "cardiovascular_strain": "Cardiovascular strain",
    "dehydration": "Dehydration",
    "low_blood_sugar": "Low blood sugar",
    "high_blood_sugar": "High blood sugar",
    "optic_disc_change": "Possible optic disc swelling (eye)",
    "kidney_stone_risk": "Blood in urine: kidney stone risk",
    "urinary_infection": "Possible urinary infection",
    "urine_abnormal": "Unusual urine test",
    "constipation": "Constipation",
    "diarrhea": "Diarrhoea",
    "stool_blood": "Blood in stool",
}
ENGINE_CONDITIONS = list(ENGINE_CONDITION_LABELS)

# ---------------------------------------------------------------------------
# Hard clinical limits. These override the ML model (rules win over models).
# level: "RED" = act now / contact flight surgeon, "YELLOW" = watch and act.
# ---------------------------------------------------------------------------
HARD_LIMITS = [
    # signal, operator, value, level, condition, message
    ("spo2", "<", 90.0, "RED", "hypoxia", "SpO2 below 90%"),
    ("spo2", "<", 94.0, "YELLOW", "hypoxia", "SpO2 below 94%"),
    ("core_temp", ">=", 39.0, "RED", "fever_infection", "Core temperature at or above 39.0 C"),
    ("core_temp", ">=", 38.0, "YELLOW", "fever_infection", "Core temperature at or above 38.0 C"),
    ("systolic_bp", ">=", 160.0, "RED", "cardiovascular_strain", "Systolic BP at or above 160 mmHg"),
    ("systolic_bp", "<", 90.0, "RED", "dehydration", "Systolic BP below 90 mmHg"),
    ("cabin_co2_mmhg", ">", 6.0, "RED", "co2_exposure", "Local ppCO2 above 6 mmHg"),
    ("cabin_co2_mmhg", ">", 3.0, "YELLOW", "co2_exposure", "Local ppCO2 above 3 mmHg (NASA-STD-3001 1-h limit)"),
]
# Resting HR limits only apply when activity_level < 0.2
RESTING_HR_RED = 120.0
RESTING_HR_YELLOW = 100.0

# ---------------------------------------------------------------------------
# Mission / long-term limits
# ---------------------------------------------------------------------------
CAREER_RADIATION_LIMIT_MSV = 600.0   # NASA-STD-3001 Vol 1 [V1 4030]
SPE_EVENT_LIMIT_MSV = 250.0          # per solar particle event
CO2_ONE_HOUR_LIMIT_MMHG = 3.0        # NASA-STD-3001 Vol 2 [V2 6004]
BMD_LOSS_ALERT_PCT = 5.0             # flag when projected hip BMD loss passes this
DAILY_FLUID_TARGET_ML = 2500
SLEEP_TARGET_H = 8.0
ARED_TARGET_MIN_WEEK = 360           # resistive exercise target (6 x 60 min)
AEROBIC_TARGET_MIN_WEEK = 240

# Hours of history the engine needs for one assessment
WINDOW_HOURS = 24
BASELINE_DAYS = 3
