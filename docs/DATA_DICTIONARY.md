# Data Dictionary

The demo astronaut is **fictional and simulated**. Real datasets set its statistics (`docs/DATASETS.md`, notebook 08), and the radiation
series is a replay of real measurements. `data/demo/sources.json` records the origin of every signal and the API returns it with each value.

| Source tag | Meaning | Signals |
|---|---|---|
| `simulated`, calibrated on **PMData** | generated to match real people's statistics | resting HR, sleep, fatigue, mood, stress, hourly heart rate |
| `simulated`, calibrated on **NASA OSDR EDA** | block bootstrap of real ISS CO2 | cabin CO2 |
| `real`, **NASA/JPL MSL RAD** replayed | Curiosity's measured dose rate, 7 Mar – 20 May 2024 | radiation dose rate and dose |
| `simulated`, **published normal ranges** | in no real dataset | BP, SpO2, temperature, respiration, HRV, reaction time, fluids, blood glucose |

## Files
| File | Content |
|---|---|
| `data/demo/crew.json` | `mission` object + `crew[]` with the one fictional astronaut |
| `data/demo/telemetry.csv` | 1,800 hourly rows = 75 days × 24 h |
| `data/demo/daily.csv` | 75 daily rows |
| `data/demo/planted_cases.json` | ground truth of the 4 planted cases (evaluation and replay only; the engine never reads it) |
| `data/demo/sources.json` | origin of every signal |
| `data/demo/eye_exams/*.png`, `eye_exams.json` | synthetic fundus photos on mission days 1, 30 and 60 (the day-60 one shows early swelling) |
| `data/user/` (git-ignored) | the astronaut's own answers (`answers.json`) and uploaded eye photos |
| `data/demo/api_snapshots/` | saved API responses for frontend mock mode (`at/<mark>/` for replay) |
| `data/demo_v0/` | the earlier purely simulated four-person crew, kept for the baseline comparison |
| `data/processed/*.parquet` | tidy tables from the real datasets (git-ignored; rebuilt by notebooks 01, 04, 06) |

## Hourly telemetry (`telemetry.csv`)
| Column | Unit | How it is made |
|---|---|---|
| `timestamp`, `astronaut_id`, `mission_day`, `hour` | — | mission starts 2026-08-31 00:00; `UH-01`…`UH-04` |
| `heart_rate` | bpm | the day's resting HR + real hour-of-day profile from PMData + scatter (SD 6.9 bpm, from real night hours) + 70 × activity during exercise |
| `hrv_rmssd`, `spo2`, `resp_rate`, `systolic_bp`, `diastolic_bp`, `core_temp`, `pvt_reaction_ms` | ms, %, /min, mmHg, °C, ms | v0 simulator: personal baseline, circadian pattern, sleep and exercise effects, noise |
| `activity_level` | 0–1 | 0.02 asleep; awake scatter tied to heart rate; 0.55–0.85 in exercise hours |
| `is_asleep` | 0/1 | each night ends at 06:00 and lasts `round(sleep_minutes / 60)` hours |
| `exercise_type` | none / resistive / aerobic | resistive ~09:00, aerobic ~15:00, frequency from the weekly plan |
| `fluid_intake_ml` | ml/h | v0 simulator (~150 awake) |
| `cabin_co2_mmhg` | mmHg | block bootstrap of real ISS mission RR-23 (mean 1.6); mission days 24–33 carry RR-1's highest real 10-day stretch |
| `radiation_ugy_per_day` | µGy/day | **real** MSL RAD detector E hourly dose rate, replayed; empty hours take the previous day's median |
| `radiation_msv` | mSv in this hour | `radiation_ugy_per_day × 3.0 / 1000 / 24` |

## Daily table (`daily.csv`)
| Column | Unit | How it is made |
|---|---|---|
| `astronaut_id`, `date`, `mission_day` | — | |
| `resting_hr` | bpm | AR(1) around a personal mean: between-people SD 6.8, within-person SD 2.1, lag-1 0.85 (all from PMData) |
| `sleep_minutes` | min | personal mean + resampled real night-to-night residuals, clipped to 180–600 |
| `fatigue`, `mood`, `stress` | 1–5, **5 = best**, 3 = normal | Markov chain with a real PMData person's day-to-day transition matrix |
| `headache` | 0/1 | scripted for the planted cabin case only |
| `blood_glucose_mg_dl` | mg/dL, fasting | normal around a personal mean of about 90, SD 6 (published range 70–99) |
| `urine_sg`, `urine_ph` | specific gravity, pH | normal(1.017, 0.004) clipped to 1.003–1.029; normal(6.2, 0.5) |
| `urine_blood`, `urine_protein`, `urine_glucose`, `urine_ketones`, `urine_leukocytes` | dipstick pad 0–3 (negative, trace, +, ++) | mostly negative, rare trace |
| `urine_nitrite`, `stool_blood`, `flank_pain`, `vision_change` | 0/1 | 0 unless answered by the user |
| `stool_bristol`, `stool_count` | Bristol type 1–7, motions a day | published type distribution (mostly 3–5); Poisson(1.1) clipped to 0–3 |

A day's row counts as known to the engine from 08:00 of that day.

## Crew profile (`crew.json → crew[]`)
`astronaut_id, name, role, agency, age, sex, mass_kg, prior_career_dose_msv, protein_g_per_kg, vitamin_d_ng_ml,
ared_minutes_week, aerobic_minutes_week, baseline{8 vitals + simulator params}`.
`baseline` vital values = median of awake, resting hours on mission days 1–3.

## Demo astronaut and planted cases
One fictional astronaut, **UH-01 Nadia Farouk**, alone on the mission, carries all four planted cases at different times:

| Case | Mission days | What was planted |
|---|---|---|
| Cabin CO2 with headache reports | 24–33, headaches from day 27 | the highest real 10-day CO2 stretch of ISS mission RR-1; headache reports, fatigue ≤ 2 |
| Slow drift (illness onset) | 40–49 ramp, held to 54, then resolved | resting HR +6 bpm, sleep −60 min, fatigue one point worse |
| Odd combination | 62–68 | mood −1, stress −1, sleep −55 min |
| Eye exam: optic disc swelling | photo on day 60 | synthetic photo with an early swollen disc (days 1 and 30 normal) |
| Solar storm | day 75 from 05:00 (under way "now") | the real 20 May 2024 storm, unscaled |

## Real-data tables (`data/processed/`)
| File | Rows | Columns |
|---|---|---|
| `pmdata_daily.parquet` | 2,398 person-days | `person, date`, resting HR, sleep, sleep score, self-reports, steps, active minutes, `exercised`, `injury` |
| `pmdata_hourly_hr.parquet` | hourly | `person, hour, hr_mean, hr_min, hr_max, n` |
| `msl_rad_hourly.parquet`, `msl_rad_daily.parquet` | 25,097 hours / 1,046 days | `dose_b, dose_b_rtg, dose_e` (µGy/day), `n`, `local_hour` |
| `iss_cabin.parquet` | 24,446 hours, 14 missions | temperature, humidity, CO2 (ppm and `co2_mmhg`) for ISS and ground |
| `iss_radiation_daily.parquet` | 467 days, 11 missions | `gcr, saa, total` (mGy/day) |

## v0 simulator (baseline and the simulated-only vitals)
`ml/sol_ml/simulate.py` scripts six conditions (sleep deprivation, dehydration, CO2 exposure, cardiovascular strain, fever, hypoxia) with fixed
signatures and trains the v0 classifier on them. The v2 crew does not use those episodes; it only takes the simulator's nominal vitals.
The bone and muscle cohort (1,500 simulated missions, hip BMD ≈ 1.55 %/month × (1 − 0.55 × ARED/360)) still trains the projection model.
