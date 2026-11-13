# CLAUDE.md — Sol Health

Context for Claude Code. Read in this order:
1. this file
2. `docs/CHALLENGE.md`: the official NASA brief and our coverage gaps
3. `docs/DATASETS.md`: the real data the team agreed on
4. `docs/NOTEBOOKS.md`: the analysis and modelling plan, **your first job**
5. `docs/BUILD_PLAN.md`: the step-by-step prompts

## What we are building

**Sol Health** is health-monitoring software for astronauts, built for the NASA Space Apps 2026 challenge
*"Create Health Monitoring Software for Astronauts on Space Missions"* (Cairo, 14–15 Nov 2026). It **gathers health
indicators** and lets each astronaut **evaluate and act on** their health, offline, because deep-space crews can't
wait for Earth. For every crewmember it answers three questions:
1. **How am I right now?** Every indicator compared with *my own* baseline.
2. **Is something wrong, and why?** GREEN / YELLOW / RED with a one-sentence reason.
3. **What do I do?** A prioritised action checklist (self / crew / crew medical officer / flight surgeon) and a daily plan.

## Data and model strategy (team decision; do not change it without asking)

NASA has no public daily vitals for astronauts. So **real data calibrates a crew generator, and the engine runs on the generated crew**:
- **PMData** (16 real people, Fitbit + self-reported mood/fatigue/stress) → the astronaut's body.
- **MSL RAD** (Curiosity rover, NASA/JPL) → radiation on Mars.
- **OSDR EDA** (ISS cabin, NASA Ames) → CO2, temperature, humidity, ISS radiation.
- Published clinical ranges → BP, SpO2, temperature, glucose (simulated only).

Models must be **statistical and explainable**, with **no deep learning**: personal robust baseline + CUSUM + Isolation Forest
(body), dose counter + SPE detector (radiation), rolling averages + rule-based environmental gate (cabin).
Success is measured by **false alarms per person per month on real PMData** and **detection delay on planted cases**.

## Current state of the repo

| Part | Where | Status |
|---|---|---|
| Download scripts | `data/fetch/` | Ready. PMData, MSL RAD and OSDR EDA are all scripted (`fetch_osdr_eda.py` uses the public EDA API) |
| Notebooks | `notebooks/` (sources in `notebooks/_src/`, build with `make.py`) | **Done, 00–09**, each with a Decision cell |
| Engine + API | `ml/sol_ml/engine.py`, `ml/api/main.py` | **v2 done**: chosen models from `models/engine_config.json`, API shape kept and extended (`docs/API.md`) |
| v0 baseline | `ml/sol_ml/engine_v0.py`, `data/demo_v0/` | Kept only for the comparison in notebook 09 |
| Action protocols | `ml/sol_ml/protocols.py`, `indicators.py` | Extended (SPE shelter, likely environmental, drift, mood, glucose); indicator explainer catalogue |
| Demo crew | `data/demo/` | Data-calibrated crew with 4 planted cases (notebook 08) + `api_snapshots/` for mock mode |
| Frontend | `frontend/` | **Done**: React + Vite dashboard per `docs/PRD.md` (sol-strip replay, body figure, check-in, explainer cards, offline snapshot mode). Run with `npm --prefix frontend run dev` |

## Work order
1. **Get the data:** `python data/fetch/fetch_pmdata.py`, `python data/fetch/fetch_msl_rad.py 2024 2025 2026`, then the
   OSDR EDA download (`python data/fetch/fetch_osdr_eda.py`; manual fallback in `data/fetch/OSDR_EDA_DOWNLOAD.md`).
2. **Notebooks 00 → 09**, exactly as specified in `docs/NOTEBOOKS.md`. Each one explores the data, compares several models with the shared
   evaluation protocol, and ends with a **Decision** cell. Put reusable code in `ml/sol_ml/data/` and `ml/sol_ml/detectors/` with unit tests.
3. **Refactor the engine** to the chosen models via `models/engine_config.json`. **Keep the API response shape** (`docs/API.md`) so the
   frontend plan stays valid. Add the new alert kinds (SPE shelter, environmental gate) and the challenge's missing indicators
   (blood glucose, mood, daily sleep hours, see `docs/CHALLENGE.md`).
4. **Frontend** per `docs/PRD.md`, plus the challenge extras: clickable body figure, measurement check-in form, indicator explainer cards.

## Hard rules
- **Never present simulated values as real.** Each value shown in the app is tagged with its source: real dataset or simulated.
- **No medical logic in the frontend.** Status, thresholds and actions come from the API.
- Every alert carries a **one-sentence reason** naming the signal, how far from normal, and for how long.
- Raw data stays in `data/raw/` (git-ignored). Processed tables go in `data/processed/` (parquet).
- Notebooks run headless (`jupyter nbconvert --execute`), seed 42, figures saved to `reports/figures/`.
- Cite data in the app's About page and the README: PMData (Thambawita et al. 2020), NASA OSDR EDA credit line, and MSL RAD (NASA/JPL, Hassler et al.).
- If a dataset fact in `docs/DATASETS.md` is marked "not confirmed" (variable names, CO2 unit, sampling rate), confirm it from the files and update the doc.
- If something in the plan doesn't work with the real data (too sparse, wrong units), **say so in the notebook's Decision cell and in chat**. Don't quietly change the plan.

## Commands
```bash
pip install -r ml/requirements.txt
python data/fetch/fetch_pmdata.py
python data/fetch/fetch_msl_rad.py 2024 2025 2026   # add --limit 30 for a quick test
python data/fetch/fetch_osdr_eda.py
python data/fetch/inspect_sources.py                 # print real variable names, units, sampling
jupyter lab notebooks/
jupyter nbconvert --to notebook --execute --inplace notebooks/NN_name.ipynb
cd ml && python -m pytest -q                         # must stay green
cd ml && uvicorn api.main:app --reload --port 8000   # API docs at /docs
```

## Repo map
```
CLAUDE.md                     this file
docs/CHALLENGE.md             NASA brief + coverage gaps
docs/DATASETS.md              sources, licenses, units, gotchas
docs/NOTEBOOKS.md             notebook-by-notebook spec + evaluation protocol
docs/BUILD_PLAN.md            ready-to-paste prompts
docs/PRD.md, API.md           frontend spec and API contract (keep the response shape)
docs/MODELS.md                model cards with the final numbers (notebook 09)
docs/ARCHITECTURE.md, DATA_DICTIONARY.md, CLINICAL_PROTOCOLS.md   design docs for the v2 engine
docs/PROJECT_GUIDE_AR.md      Arabic guide to the whole project
data/fetch/                   download + inspection scripts
data/raw/                     downloaded data (git-ignored)
data/processed/               tidy parquet tables from the notebooks
data/demo/                    demo crew + api_snapshots for frontend mock mode
notebooks/                    00–09 (sources in notebooks/_src/)
ml/sol_ml/                    library code (loaders, detectors, engine, protocols)
ml/api/main.py                FastAPI
models/                       engine_config.json (after nb 09) + v0 joblib baseline
reports/figures/              notebook figures for slides
frontend/                     React dashboard (see frontend/README.md)
```
