# Sol Health

**Onboard AI medical copilot for astronauts.** NASA Space Apps 2026  *Create Health Monitoring Software for Astronauts on Space Missions*  Cairo.

A personal health app for an astronaut alone on a deep-space mission. It shows **every indicator against your own baseline**,
says **whether something is wrong and why**, tells you **what to do now**, and sends what matters to **your flight surgeon** on Earth,
who is minutes away, so you act first.

**Live demo: [sol-health.vercel.app](https://sol-health.vercel.app)** (runs on the saved demo snapshots; check-ins and eye photos need the API running locally)

## What's inside
- **Explainable engine**, tuned on real data (no deep learning; every alert gives a one-sentence reason):
  - Body: personal robust baseline + bounded CUSUM (slow drifts) + Isolation Forest (odd combinations), **1.00 false alarm per person-month on real PMData**
  - Solar-storm alarm: caught the real 20 May 2024 storm (Curiosity's RAD) in its first hour, with no unconfirmed alarm in 35 months
  - Cabin CO2 environmental gate from NASA limits, replayed on 468 days of real ISS data
  - Radiation dose counter, bone and muscle projection, fitness trend
  - Hard clinical limits for SpO2, temperature, blood pressure, glucose; urine dipstick and stool-log rules
  - Eye exam: a fundus photo check by classical image measurement against your own baseline photo (no trained model), for SANS
- **Action protocols:** prioritised checklists: what you do, and what goes to your flight surgeon (act-now alerts at once, watch alerts in the daily report)
- **FastAPI** service: today's questions (with follow-ups), saved answers, eye-photo upload, a daily brief (rules now, AI-ready), mission replay (`?at=`)
- **Notebooks 00–09:** data exploration, model comparison with a shared protocol, and a Decision cell each (`notebooks/`, figures in `reports/figures/`)
- **Demo mission:** one fictional astronaut alone on a Mars surface mission, 75 days, carrying all 4 planted test cases; statistics calibrated on real data
- **Docs** for judges (`docs/`)

## Data (real + simulated)
| Data | What it gives us |
|---|---|
| **PMData** (16 people, Fitbit + self-reports) | Real heart rate, sleep, mood, fatigue, stress |
| **MSL RAD** (NASA/JPL, Curiosity) | Real radiation on the Mars surface, incl. the May-2024 solar storm |
| **OSDR EDA** (NASA Ames, ISS) | Real ISS cabin CO2, temperature, humidity, ISS radiation |
| Published clinical ranges | BP, SpO2, temperature, glucose (simulated) |

Details, licenses and citations: [docs/DATASETS.md](docs/DATASETS.md). Get it:
```bash
pip install -r ml/requirements.txt
python data/fetch/fetch_pmdata.py
python data/fetch/fetch_msl_rad.py 2024 2025 2026
python data/fetch/fetch_osdr_eda.py
python data/fetch/inspect_sources.py
```

## Quick start
```bash
cd ml
pip install -r requirements.txt
python -m pytest -q                       # 114 tests
uvicorn api.main:app --reload --port 8000 # http://localhost:8000/docs
# optional: rebuild from the real data
python ../notebooks/_src/make.py 00 01 02 03 04 05 06 07 08 09   # notebooks (02 takes ~25 min the first time)
python -m sol_ml.train_body               # pooled Isolation Forest
python -m sol_ml.snapshots                # API snapshots for frontend mock mode
```
Then open Claude Code in the repo root and follow `docs/BUILD_PLAN.md` to build the dashboard.

## Docs
| Doc | For |
|---|---|
| [docs/CHALLENGE.md](docs/CHALLENGE.md) | The NASA brief and our coverage |
| [docs/DATASETS.md](docs/DATASETS.md) | Real data sources |
| [docs/NOTEBOOKS.md](docs/NOTEBOOKS.md) | Analysis + model comparison plan |
| [docs/PRD.md](docs/PRD.md) | Screens, user stories, acceptance criteria |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design and decision logic |
| [docs/API.md](docs/API.md) | Endpoints and response types |
| [docs/MODELS.md](docs/MODELS.md) | Model cards and metrics |
| [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md) | Signals, units, simulation |
| [docs/CLINICAL_PROTOCOLS.md](docs/CLINICAL_PROTOCOLS.md) | Thresholds, actions, references |
| [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md) | Ready-to-paste prompts for Claude Code |

## Team
Abdulrahman Hesham, Adham Ehab, Ahmed Galala, Ammar Yasser, Moamen Abdelrazek, Mohammed Elhendawy.

## Data credits
- **PMData:** Thambawita et al., *PMData: A Sports Logging Dataset*, MMSys 2020, doi:10.1145/3339825.3394926.
- **NASA OSDR EDA:** Data and visualizations are courtesy of the Environmental Data Application (EDA) (https://visualization.osdr.nasa.gov/eda/).
- **MSL RAD:** NASA/JPL, Hassler et al. (Curiosity Radiation Assessment Detector), level-2 data from NASA CDAWeb.
