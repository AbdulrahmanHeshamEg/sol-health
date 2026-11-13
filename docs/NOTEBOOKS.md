# Notebook plan: understand the data, then compare models for every part

Claude Code builds these notebooks in `notebooks/`, in order. Each notebook **explores the data first** and then
**compares several models for its part** with one shared evaluation. It ends with a written decision: which model,
which parameters, and why. Data sources are described in `docs/DATASETS.md`.

## Rules for every notebook
- **First cell (markdown):** the questions the notebook answers, the inputs, and the outputs.
- **Last cell (markdown) "Decision":** the chosen model and parameters, the numbers that justify the choice, what was rejected and why, and known limits.
- **Reusable code goes in `ml/sol_ml/`** (loaders in `sol_ml/data/`, detectors in `sol_ml/detectors/`). Notebooks import it and stay readable, not 2,000-line scripts.
- Fixed seed (`SEED = 42`). Every figure is saved to `reports/figures/<nb>_<name>.png`. Chosen parameters go to `models/engine_config.json`.
- Notebooks must run headless: `jupyter nbconvert --to notebook --execute --inplace notebooks/NN_*.ipynb`.
- Explainability is a hard requirement: every model must be able to say *why* in one sentence ("resting HR has been 2.4 robust-SD above your 14-day normal for 4 days").
- No deep learning (team decision). Simple statistics first. A more complex model wins only if it clearly beats the simple ones on the shared metrics.

## Shared evaluation protocol (Body models: notebooks 02, 03 and 09)
1. **False alarms per person-month on real PMData.** Run the detector on every participant's real data after a 14-day warm-up.
   Merge consecutive alert days into one alert *episode*. Exclude injury days ±2 days (`injury.csv`), because those are real changes.
   PMData has no medical events, so every remaining episode counts as a false alarm.
2. **Detection delay on planted cases (semi-synthetic).** Take a real person's real series, inject a known change on a random
   start day, and record how many days pass until the first alert (missed if none within 14 days). Repeat ≥ 200 injections per
   detector over all people and start days. Report the median delay, the 90th-percentile delay and the miss rate.
3. **Operating point:** sweep each detector's parameters and plot false alarms vs median delay (a trade-off curve).
   Pick the fastest setting with **≤ 1 false alarm per person-month**. The team can change this target, but write it in the decision cell.

Injected changes (amplitude scaled to each person's own robust SD so the test is fair across people):
| Name | Change |
|---|---|
| `drift_hr` | resting HR rises linearly to +2 robust SD over 7 days |
| `drift_multi` | resting HR +1.5 SD, sleep −1.5 SD, fatigue +1.5 SD together over 7 days |
| `combo_odd` | each signal within ±1.5 SD but mood ↓, stress ↑, sleep ↓ together for 5 days |
| `step_sleep` | sleep drops 2 SD overnight and stays low for 5 days |

---

## 00_setup_and_inspect.ipynb
Run `data/fetch/inspect_sources.py` logic inline. Record the **MSL RAD variable names** (dose rate B and E, time),
the **OSDR EDA CO2 unit and sampling rate**, and the PMData participant count and date range. Write them back into `docs/DATASETS.md`.

## 01_pmdata_eda.ipynb: understand the body data
- Build one tidy **daily table per person**: `resting_hr, sleep_minutes, deep_minutes, rem_minutes, sleep_score, restlessness,
  fatigue, mood, readiness, stress, soreness, sleep_quality, steps, active_minutes, exercised(bool)`, plus an `injury` flag.
  Stream `heart_rate.json`, because it is large, and aggregate it to hourly and daily mean, min and max.
- Missing data per person and variable (heatmap). How often does wellness get filled in? What gaps exist?
- Distributions per person (violins): how different are people from each other? This is the argument for personal baselines.
- Within-person behaviour: day-to-day autocorrelation (ACF), weekly patterns (weekday vs weekend), slow trends.
- Correlations between body signals and self-reports (resting HR vs fatigue, sleep vs mood) using Spearman, within person.
- What do injury days look like before and after?
- **Output:** `data/processed/pmdata_daily.parquet`, `data/processed/pmdata_hourly_hr.parquet`, and a short findings list.

## 02_body_baseline_models.ipynb: is today abnormal for *this* person?
Compare these candidates with the shared protocol:
| # | Model | Notes |
|---|---|---|
| A | Population z-score | Baseline to beat; shows why personal baselines matter |
| B | **Personal robust z** `z = (x − median₁₄) / (1.4826·MAD₁₄)`, alert at \|z\| > 3 | **Team's plan.** Sweep window 7/14/28 and threshold 2.5/3/3.5 |
| C | **CUSUM on z** (resting HR, sleep, fatigue) | **Team's plan.** Start at k = 0.5, h = 5, then tune |
| D | EWMA control chart on z | λ ∈ {0.1, 0.2, 0.3} |
| E | **Isolation Forest** on the daily z-vector (HR, sleep, mood, fatigue, stress) | **Team's plan.** Fit per person on a rolling history, or pooled on z-space; compare both |
| F | Robust Mahalanobis (MinCovDet) on the z-vector | Interpretable multivariate alternative to E |
| G | Local Outlier Factor (novelty mode) | Optional |

Also report which **single signals** carry the most detection value (ablation) and how the methods complement each other:
does C catch slow drifts that B misses, and does E or F catch `combo_odd` that B and C miss? Recommend a **combination**,
e.g. "B for spikes + C for drifts + E for odd combos", and evaluate the combination itself with the shared protocol.

## 03_deconditioning.ipynb: is fitness slipping?
The team's idea: compare heart rate in the same exercise type week to week. Candidates:
| # | Model |
|---|---|
| A | Weekly median HR per activity type + Theil–Sen slope (bpm/week) |
| B | Efficiency index for runs: HR ÷ speed (lower is fitter), weekly trend |
| C | Linear mixed model (`statsmodels` MixedLM): HR ~ week + duration + type, random intercept per person |
| D | Change-point detection on weekly HR (`ruptures`, PELT) |
Evaluate with planted gradual HR increases (+1–3 bpm/week) on real sessions: delay and false trend alarms.
Report how many people have enough sessions; this data is sparse, so say so honestly.

## 04_msl_rad_eda.ipynb: understand Mars surface radiation
- Load all CDFs into one tidy table: time, dose rate B (silicon), dose rate E (tissue). Check units (µGy/day) and gaps.
- Plot the full record: the slow GCR change over the solar cycle, the diurnal cycle (average by local hour), and the **May 2024 storm**.
- Sanity-check against the reference values (≈ 0.21 mGy/day tissue, ≈ 0.16 mGy/day silicon on a quiet day).
- B vs E relationship (ratio over time). Decide which one drives the dose counter (the team planned E).
- **Output:** `data/processed/msl_rad_hourly.parquet` and `msl_rad_daily.parquet`.

## 05_radiation_models.ipynb: dose budget and solar storm alarm
1. **Cumulative dose counter** (deterministic): absorbed → equivalent dose with Q ≈ 3.0, compared with the mission budget.
   YELLOW at 80 %, RED at 100 %. Show it for three settings: ISS (from OSDR EDA), Mars transit (1.84 mSv/day constant), and Mars surface (RAD).
2. **SPE detector**, comparing:
| # | Model |
|---|---|
| A | **Robust z of hourly dose rate vs trailing 7-day median** (team's plan) |
| B | Ratio to 7-day median > r (e.g. 2×, 3×) |
| C | CUSUM on log dose rate |
| D | EWMA |
| E | Change-point (`ruptures` PELT / window) |
   Handle the diurnal cycle, e.g. compare against the same local hour or deseasonalize, and **show the effect**.
   Evaluation: must catch the **20 May 2024** event (report the lead time from onset), count false alarms over quiet months,
   and check that the slow solar-cycle drift raises no alarms (the moving median should absorb it).
3. Recommended action text: "SPE in progress: whole crew to the storm shelter".

## 06_osdr_cabin_eda.ipynb: understand ISS cabin air
- Load the telemetry and radiation tables for each downloaded RR mission. Confirm the CO2 unit and convert to mmHg.
  Measure the sampling interval.
- Distributions (ISS vs ground), diurnal profile, autocorrelation, how often CO2 exceeds 3 mmHg (1-h mean) and 2.5 mmHg (7-day mean).
- Relationship between temperature, humidity and CO2.
- ISS radiation: GCR vs SAA vs total, daily dose rate. Compare it with Mars surface (notebook 04).
- **Output:** `data/processed/iss_cabin.parquet` and `iss_radiation_daily.parquet`.

## 07_cabin_models.ipynb: environmental gate and CO2 generator
1. **Rolling averages** (1 h and 7 days) and the **environmental gate** (rules, *not learned*; thresholds from NASA OCHMO-TB-004):
   1-h mean > 3 mmHg, or 7-day mean > 2.5 mmHg **and** headache or fatigue reported → the alert says "likely environmental"
   and the first suggestion is ventilation. Replay it over the real ISS series and report how often it would fire.
2. **CO2 generator** for the simulated crew, comparing: (A) Gaussian + diurnal sinusoid, (B) AR(1) / SARIMA, and
   (C) block bootstrap of the real series. Score each by the KS distance to the real distribution, ACF match and diurnal profile match.
   Pick the closest one.

## 08_crew_generator.ipynb: build the simulated crew from real data
- Body signals: noise level, autocorrelation and between-person spread taken from PMData (notebook 01). Self-reports come from PMData distributions.
- Cabin: the chosen CO2 generator (notebook 07). Radiation: ISS-mode from OSDR EDA and Mars-mode from MSL RAD, including a replay of the May-2024 storm shape.
- BP, SpO2, body temperature, **blood glucose** from published normal ranges, clearly labelled as simulated.
- **4 planted test cases** (proposed, so confirm with the team):
  1. *Slow drift*: resting HR ↑, sleep ↓, fatigue ↑ over 10 days (illness onset). Expected to be caught by CUSUM.
  2. *Odd combination*: mood ↓, stress ↑, sleep ↓, each within normal limits alone (behavioral health). Expected to be caught by the multivariate model.
  3. *Cabin CO2*: 7-day CO2 > 2.5 mmHg with headache reports. Expected outcome: the environmental gate says "likely environmental".
  4. *Solar storm*: radiation spike. Expected outcome: the SPE alarm sends the whole crew to the shelter.
- Validation plots: generated vs real distributions and ACFs for every signal.
- **Output:** `data/demo/` (replaces the old purely-simulated demo crew) and `data/demo/planted_cases.json` (ground truth for evaluation only).

## 09_engine_evaluation.ipynb: the final numbers for the judges
- Run the full engine (chosen models from 02, 03, 05 and 07) on (a) real PMData and (b) the generated crew.
- Final table: false alarms per person-month (real PMData), detection delay and miss rate per planted case, and SPE lead time on May 2024.
- **Baseline comparison:** the earlier v0 engine (`HistGradientBoosting` trained on simulated labels, `models/risk_classifier.joblib`).
  Show honestly why it doesn't transfer, or where it does.
- Example alert sentences for each case (what the astronaut would read).
- Export `models/engine_config.json` and update `ml/sol_ml/engine.py` to use it **without changing the API response shape** in `docs/API.md`.
- Update `docs/MODELS.md` with the final model cards and numbers.
