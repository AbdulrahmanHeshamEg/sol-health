# Architecture

```
 Sensors / wearables (simulated)            Ground (delayed link)
   HR, HRV, SpO2, BP, resp, temp,                 flight surgeon
   PVT test, activity, sleep,                          ^
   fluids, cabin CO2, dosimeter                        | summaries at comm pass
            |                                          |
            v                                          |
 +-----------------------------------------------------------------+
 |  Onboard Sol Health (runs fully offline)                     |
 |                                                                  |
 |  telemetry (hourly rows)                                         |
 |        |                                                         |
 |        v                                                         |
 |  features.py  personal baseline (days 1-3) -> deltas,            |
 |               6 h rolling means, sleep/fluid/CO2 context         |
 |        |                                                         |
 |        +--> 1. Hard clinical limits (config.HARD_LIMITS)  ---+   |
 |        +--> 2. Risk classifier (7 conditions)            ----+   |
 |        +--> 3. Anomaly detector (personal "unusualness") ----+   |
 |                                                              v   |
 |                                engine.assess(): level, score,    |
 |                                condition, alerts, drivers        |
 |                                              |                   |
 |                                protocols.py: actions + daily plan|
 |                                                                  |
 |  4. Deconditioning forecaster (bone, muscle)  engine.forecast_*  |
 |  5. Radiation accounting (deterministic)      engine.radiation_* |
 |                                                                  |
 |  FastAPI (ml/api/main.py)  --JSON-->  React dashboard (frontend/) |
 +-----------------------------------------------------------------+
```

## Data flow per request
1. API loads the astronaut's hourly history up to `at` (or latest).
2. `build_features()` computes deviations from the astronaut's personal baseline (stored in `crew.json`, calibrated on mission days 1–3, awake resting hours).
3. The engine combines rules and models (below) and attaches protocol actions.
4. The frontend renders. It never decides status itself.

## How the outputs combine (decision logic)
1. **Rules first.** Any hard limit in `config.HARD_LIMITS` (e.g. SpO2 < 90 %, core temp ≥ 39 °C, ppCO2 > 6 mmHg) raises its level directly. Rules always win over models.
2. **Risk classifier.** Probabilities are averaged over the last 3 hours to avoid flicker. If a non-nominal condition has p ≥ 0.5 → YELLOW.
3. **Escalation by model alone to RED** only if the same condition has p ≥ 0.9 **and** the anomaly score ≥ 0.9 for **3 consecutive hours**.
4. **Final status** = worst of rule level and model level.
5. **Primary condition** = condition of the first RED rule, else the model's condition (if it raised a level), else the first YELLOW rule's condition, else `nominal`.
6. **Health score** = `100 − 40·P(abnormal) − 25·anomaly − 20·(#RED rules) − 8·(#YELLOW rules)`, clipped to 0–100.
7. **Drivers** = the 3 vitals whose 6 h mean deviation from baseline is largest in noise units (simple, explainable).

## Why this design
- **Personal baselines:** resting HR of 52 vs 68 bpm are both normal; deviations from *your* normal are what matter.
- **Rules + ML:** rules give guaranteed, auditable behaviour for clear emergencies; ML catches multi-signal patterns (e.g. mild dehydration: HR up, BP down, fluids low) before any single limit breaks.
- **Two ML views:** the classifier names *known* conditions; the anomaly detector flags *unknown* "this isn't normal for you" states.
- **Offline-first:** small scikit-learn models (< 7 MB total), no cloud calls, CPU inference in milliseconds.

## Tech
Python 3.11+, scikit-learn 1.9, pandas, FastAPI. Frontend: React + Vite + TypeScript + Tailwind + Recharts.
