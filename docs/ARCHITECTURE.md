# Architecture

```
 REAL DATA (calibration and evaluation)                     GENERATED ASTRONAUT (what the app shows)
   PMData      16 people: resting HR, sleep, self-reports ─┐
   OSDR EDA    ISS cabin CO2, ISS radiation               ─┼─> notebooks 00-09 ──> models/engine_config.json
   MSL RAD     Mars surface dose rate, May 2024 storm     ─┘         │                models/body_iforest.joblib
                                                                     v
                                               sol_ml/sim/crew.py ──> data/demo/ (telemetry.csv hourly, daily.csv,
                                               (statistics from real data;      crew.json, sources.json, planted_cases.json)
                                                radiation = real RAD replay)
                                                                     │
 +-------------------------------------------------------------------v-----------------------------+
 |  Onboard Sol Health (runs fully offline)                                                         |
 |                                                                                                  |
 |  engine.prepare(hourly, profile, daily)   causal tables, computed once                           |
 |     body       personal robust z · bounded CUSUM · pooled Isolation Forest      (daily)          |
 |     cabin      1-hour and 7-day CO2 means                                        (hourly)        |
 |     radiation  dose-rate ratio to the trailing 7-day median                      (hourly)        |
 |                                                                                                  |
 |  engine.assess_at(prepared, hour)                                                                |
 |     hard clinical limits  ─┐                                                                     |
 |     body alerts            ├─> status = worst level · one-sentence reason per alert              |
 |     environmental gate     │   body systems (figure) · indicators with source tags               |
 |     storm alarm           ─┘   actions (protocols.py) · daily plan                               |
 |                                                                                                  |
 |  forecast: bone/muscle projection + fitness trend     radiation: dose counter + storm level      |
 |                                                                                                  |
 |  FastAPI (ml/api/main.py)  ──JSON──>  React dashboard (frontend/)                                |
 +--------------------------------------------------------------------------------------------------+
```

## Code map
| Path | Role |
|---|---|
| `ml/sol_ml/data/` | loaders for the real datasets (`pmdata`, `msl_rad`, `osdr_eda`) |
| `ml/sol_ml/detectors/` | `baseline` (personal z), `univariate`, `bounded`, `multivariate`, `body`, `evaluation` (shared protocol), `deconditioning`, `radiation`, `cabin` |
| `ml/sol_ml/sim/` | `crew` (the data-calibrated demo astronaut), `co2` (cabin CO2 generators) |
| `ml/sol_ml/engine.py` | the v2 engine; reads `models/engine_config.json` |
| `ml/sol_ml/protocols.py`, `indicators.py` | action checklists; indicator explainer catalogue and measurement schedule |
| `ml/sol_ml/engine_v0.py`, `train.py`, `simulate.py`, `features.py` | the v0 baseline and its simulator (the simulator still supplies vitals that exist in no real dataset) |
| `notebooks/_src/*.py` → `notebooks/*.ipynb` | notebook sources and the executed notebooks (`make.py` builds and runs them) |

## Data flow per request
1. The API holds one `Prepared` object for the astronaut: every table in it is **causal** (row *t* uses only data up to *t*).
2. `at=<timestamp>` picks the hourly row; a day's check-in and night summary count as known from 08:00.
3. `assess_at` collects alerts from the rules, the body models, the gate and the storm alarm, and attaches actions.
4. The frontend renders. It never decides status, thresholds or actions itself.

Because the tables are causal, replaying any earlier moment costs about 1 ms and gives exactly what the engine would have said then.

## Decision logic
1. **Hard limits first** (`config.HARD_LIMITS`, glucose limits, low-mood rule). Rules always win over models.
2. **Body models** (spike, drift, combination) and the **fitness trend** raise YELLOW only.
3. **Environmental gate:** CO2 high + headache or fatigue report → YELLOW "likely environmental", ventilation first. A fatigue-driven body alert during high CO2 gets the same note.
4. **Storm alarm:** dose rate ≥ 1.3× normal → YELLOW; ≥ 2× → RED "go to the storm shelter now".
7. **Escalation:** RED is sent to the flight surgeon at once (arrives after the communication delay); YELLOW goes in the daily report at 20:00.
5. **Status** = worst level. **Primary condition** = the condition of the most severe alert.
6. Every alert has `reason` (one sentence: signal, how far, how long), `kind`, `hazard` (NASA's five hazards) and, for models, the model name.

## Why this design
- **Personal baselines:** 91 % of the variance of resting HR is between people (notebook 01). A population threshold measures who you are, not how you are.
- **Rules + statistics:** rules give auditable behaviour for clear emergencies; the statistical models watch for slow or combined changes.
- **Each model does one job** and can say why in a sentence. Nothing is a black box, and nothing was trained on invented labels.
- **Real data sets the numbers:** thresholds were tuned against false alarms on real people, not against a simulator.
- **Offline-first:** numpy, pandas and one small scikit-learn forest (0.5 MB). No cloud calls.

## Tech
Python 3.13, numpy, pandas, scikit-learn 1.9, scipy, statsmodels, ruptures, FastAPI. Frontend: React + Vite + TypeScript + Tailwind + Recharts.
