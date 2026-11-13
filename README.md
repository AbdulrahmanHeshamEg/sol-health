# Sol Health

**Onboard AI medical copilot for astronauts.** NASA Space Apps 2026 — *Create Health Monitoring Software for Astronauts* — Cairo.

For every crewmember, Sol Health shows **all vitals against their own baseline**, says **whether something is wrong and why**,
and tells them **what to do now** — offline, because deep-space crews cannot wait for Earth.

## What's inside
- **v0 engine** (simulated data, being replaced by the notebook-selected models), with a rules engine
  - Risk classifier (7 conditions: sleep debt, dehydration, CO2 exposure, cardiovascular strain, fever, hypoxia, nominal) — macro F1 0.94 on held-out simulated astronauts
  - Personal anomaly detector (Isolation Forest) — "unusual for *you*"
  - Bone & muscle deconditioning forecaster with uncertainty band and an exercise what-if
  - Radiation dose tracking vs NASA's 600 mSv career limit
- **Action protocols:** prioritised checklists for the astronaut, crew, CMO and flight surgeon
- **FastAPI** service with mission replay (`?at=`)
- **Demo mission:** 4 fictional crew, 75 days of hourly synthetic telemetry, scripted episodes
- **Docs** for judges and for Claude Code (`CLAUDE.md`, `docs/`)

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
python data/fetch/fetch_msl_rad.py 2024 2026
# OSDR EDA: manual, see data/fetch/OSDR_EDA_DOWNLOAD.md
python data/fetch/inspect_sources.py
```

## Quick start
```bash
cd ml
pip install -r requirements.txt
python -m pytest -q                       # 4 tests
uvicorn api.main:app --reload --port 8000 # http://localhost:8000/docs
# optional: retrain everything + regenerate demo data (~30 s)
python -m sol_ml.train
```
Then open Claude Code in the repo root and follow `docs/BUILD_PLAN.md` to build the dashboard.

## Docs
| Doc | For |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Claude Code context: what exists, what to build, rules |
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
Abdulrahman Hesham (lead), Adhm Ehab, Ahmed Galala, Ammar Yasser, Moamen Abdelrazek, Mohammed Elhendawy.

## Disclaimer
All astronauts and data are **synthetic and fictional**. Sol Health is a decision-support prototype, not a medical device.
