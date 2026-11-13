# Model Cards

> **Status: v0 baseline.** These cards describe the first prototype, which was trained only on simulated data with a
> supervised classifier. The team's agreed approach (`docs/DATASETS.md`, `docs/NOTEBOOKS.md`) uses real data and
> explainable detectors. Notebook 09 compares the two, and this file is rewritten with the final models and numbers.

Three trained models plus one deterministic calculator. Train everything with
`cd ml && python -m sol_ml.train` (≈ 30 s on a laptop CPU, seed 42). Metrics are written to
`models/metrics.json`; the numbers below come from that file.

> **Important limitation.** All models are trained and tested on *synthetic* data from our own simulator.
> High scores show the pipeline works and the signatures are learnable — they are **not** evidence of
> real-world clinical accuracy. Real deployment would need validation on analog/flight data
> (e.g. NASA Lifetime Surveillance of Astronaut Health, bed-rest and Antarctic analog studies).

---

## 1. Risk classifier — "what is probably wrong?"
| | |
|---|---|
| File | `models/risk_classifier.joblib` → `{model, features, classes}` |
| Algorithm | scikit-learn `HistGradientBoostingClassifier` (300 iterations, lr 0.08, 31 leaves, L2 1.0), balanced sample weights |
| Input | 33 features for one astronaut-hour (`features.py`): 8 raw vitals, 8 deviations from personal baseline, 8 six-hour rolling deviations, HR excess beyond activity, sleep in last 24 h, fluids last 6/24 h, CO2 now and 6 h mean, activity, asleep flag |
| Output | probabilities for 7 classes: nominal, sleep_deprivation, dehydration, co2_exposure, cardiovascular_strain, fever_infection, hypoxia. The engine averages the last 3 hours. |
| Training data | 30 simulated astronauts × 120 days hourly (86,400 rows), random episodes |
| Test data | 8 **different** simulated astronauts × 120 days (23,040 rows) — astronaut-level split, so no person appears in both |

**Held-out results**
| Metric | Value |
|---|---|
| Macro F1 | 0.940 |
| Weighted F1 | 0.979 |
| AUROC, abnormal vs nominal (1 − P(nominal)) | 0.994 |

| Condition | Precision | Recall | F1 | Support (hours) |
|---|---|---|---|---|
| nominal | 0.993 | 0.983 | 0.988 | 19491 |
| sleep_deprivation | 0.879 | 0.950 | 0.913 | 482 |
| dehydration | 0.824 | 0.910 | 0.865 | 693 |
| co2_exposure | 0.993 | 0.993 | 0.993 | 575 |
| cardiovascular_strain | 0.853 | 0.940 | 0.895 | 587 |
| fever_infection | 0.956 | 0.969 | 0.962 | 699 |
| hypoxia | 0.951 | 0.973 | 0.962 | 513 |

Most errors are at the start and end of episodes (the 3 h ramps) and between mild dehydration and
cardiovascular strain, which share "HR up" — the classic clinical ambiguity. CO2 is near-perfect because the
cabin CO2 sensor is an input; in reality CO2 symptoms also overlap with microgravity fluid-shift headaches.

## 2. Anomaly detector — "is this unusual for *this* person?"
| | |
|---|---|
| File | `models/anomaly_detector.joblib` → `{model, features, scale}` |
| Algorithm | `IsolationForest` (300 trees), trained on **nominal hours only** (73,006 rows) |
| Input | 20 deviation features (deltas, rolling deltas, HR excess, activity, asleep) — no context signals |
| Output | 0–1 score: raw isolation score rescaled so 0 = median nominal hour, 1 = 99.5th percentile of nominal |
| Why | Catches conditions the classifier never saw (unknown unknowns) |

| Metric (held-out astronauts) | Value |
|---|---|
| AUROC abnormal vs nominal | 0.903 |
| Flag rate at score ≥ 0.5 — nominal hours | 6.5 % |
| Flag rate at score ≥ 0.5 — abnormal hours | 68.5 % |

The engine uses it for escalation (RED needs anomaly ≥ 0.9 for 3 h) and in the health score, never as a stand-alone alarm.

## 3. Deconditioning forecaster — "how much bone and muscle will I lose?"
| | |
|---|---|
| File | `models/deconditioning.joblib` → `{features, targets: {bmd_loss_pct_month, muscle_loss_pct_month} × {median, q10, q90}}` |
| Algorithm | `GradientBoostingRegressor` × 6 (squared error for median; quantile loss α = 0.1 and 0.9 for the band) |
| Input | mission month, age, sex, ARED min/week, aerobic min/week, protein g/kg/day, vitamin D ng/ml |
| Output | monthly loss rate (%), projected cumulative loss at `mission_day + horizon`, and a what-if with ARED at the 360 min/week target |
| Data | 1,500 simulated missions, monthly rows; split by mission (5,475 train / 1,368 test) |

| Target | MAE (%/month) | MAE of "predict the mean" baseline | q10–q90 coverage (ideal 0.80) |
|---|---|---|---|
| Hip BMD loss | 0.098 | 0.215 | 0.79 |
| Thigh muscle loss | 0.152 | 0.331 | 0.75 |

Projection assumes a constant monthly rate (linear). Real bone loss may slow over very long missions.

## 4. Radiation accounting (deterministic, no ML)
`engine.radiation_status()` sums hourly dosimeter readings, adds prior career dose, projects to mission end with the
7-day average rate, and compares with the NASA career limit of 600 mSv and the 250 mSv per-SPE limit.
YELLOW at ≥ 80 % projected, RED at ≥ 100 % or during a solar particle event (last-24 h dose > 3× the assumed daily rate).

## How the outputs combine
See `ARCHITECTURE.md` → "How the outputs combine". In short: hard limits win; models raise YELLOW; models reach RED
only when highly confident and highly anomalous for 3 consecutive hours.

## Reproducibility
- Seed 42 for training, seed 7 for the demo crew. Same code + seed → same files.
- `ml/requirements.txt` pins scikit-learn 1.9.1 (joblib files must be loaded with the same major version).
- Tests: `cd ml && python -m pytest -q` checks demo scenarios, rule override, all endpoints and replay.

## Ideas for after the hackathon
Sequence models (temporal CNN / transformer) on raw minute-level signals; per-astronaut online calibration;
conformal prediction for calibrated uncertainty; validation on public analog datasets; an onboard LLM that
explains the assessment in natural language (the engine already provides the structured facts it would need).
