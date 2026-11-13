# Build Plan for Claude Code

Run these prompts in order inside Claude Code, from the repo root. Commit after each step. If a step fails,
paste the error back and ask Claude Code to fix it before moving on.

# Phase A: data and notebooks (do this first)

## A0: Orient
```
Read CLAUDE.md, docs/CHALLENGE.md, docs/DATASETS.md and docs/NOTEBOOKS.md. Summarise the data strategy, the models
for each part, and the two success metrics in 10 lines. Don't write code yet.
```

## A1: Get the data
```
Install ml/requirements.txt. Run data/fetch/fetch_pmdata.py and data/fetch/fetch_msl_rad.py 2024 2026.
Then run data/fetch/inspect_sources.py and update the "not confirmed" items in docs/DATASETS.md (MSL RAD variable
names, PMData participant count and date range). Tell me when to do the OSDR EDA manual download and which RR missions
look longest.
```
(Human: follow `data/fetch/OSDR_EDA_DOWNLOAD.md`, put the files in `data/raw/osdr_eda/`, then tell Claude Code.)

## A2: Understand the body data
```
Build notebooks/00_setup_and_inspect.ipynb and notebooks/01_pmdata_eda.ipynb exactly as in docs/NOTEBOOKS.md.
Put loaders in ml/sol_ml/data/pmdata.py with tests. Execute the notebooks headless and show me the key findings
and figures.
```

## A3: Body models, comparing several per part
```
Build notebooks/02_body_baseline_models.ipynb and 03_deconditioning.ipynb as in docs/NOTEBOOKS.md. Implement every
candidate detector in ml/sol_ml/detectors/ with tests, and use the shared evaluation protocol (false alarms per
person-month on real PMData, detection delay on planted changes). Plot the trade-off curves. Finish each notebook with
a Decision cell and show me the comparison table.
```

## A4: Radiation
```
Build notebooks/04_msl_rad_eda.ipynb and 05_radiation_models.ipynb as in docs/NOTEBOOKS.md. The SPE detector must
catch the 20 May 2024 event. Compare all candidates and handle the diurnal cycle. Show me the comparison table and
the May-2024 plot.
```

## A5: Cabin air (after the OSDR EDA download)
```
Build notebooks/06_osdr_cabin_eda.ipynb and 07_cabin_models.ipynb as in docs/NOTEBOOKS.md. Confirm the CO2 unit and
sampling rate first and update docs/DATASETS.md. Compare the three CO2 generators.
```

## A6: Crew generator and final evaluation
```
Build notebooks/08_crew_generator.ipynb and 09_engine_evaluation.ipynb as in docs/NOTEBOOKS.md. Ask me to confirm
the 4 planted cases before generating. Produce the final numbers table, compare against the v0 classifier baseline,
and write models/engine_config.json.
```

# Phase B: engine refactor

## B1: Engine on the chosen models
```
Refactor ml/sol_ml/engine.py to use models/engine_config.json and the chosen detectors. Keep the API response shape
in docs/API.md. Add SPE-shelter and environmental-gate alerts, blood glucose, mood and daily sleep hours, and a
one-sentence reason for every alert. Regenerate data/demo and the api_snapshots, update the tests, docs/MODELS.md
and docs/ARCHITECTURE.md.
```

# Phase C: frontend

## Step 0: Orient
```
Read CLAUDE.md, docs/PRD.md, docs/API.md and docs/CHALLENGE.md. Start the API (cd ml && uvicorn api.main:app --port 8000),
call /api/crew and one /assessment, and summarise what the frontend must show. Don't write code yet.
```

## Step 1 — Scaffold + data layer (15 min)
```
Scaffold frontend/ with Vite + React + TypeScript + Tailwind + Recharts + React Router + TanStack Query.
Create src/api/types.ts from the TypeScript interfaces in docs/API.md and src/api/client.ts with one function
per endpoint. Every function takes an optional `at` timestamp. Add mock mode: copy data/demo/api_snapshots/*.json
to frontend/public/mock/ and fall back to them when VITE_USE_MOCK=true or the API fails.
Add a dark mission-control theme and a StatusChip component (GREEN/YELLOW/RED with word + icon).
```

## Step 2 — Crew Overview (20 min)
```
Build the Crew Overview page (docs/PRD.md section 4.1): mission header, crew cards from /api/crew in the order
returned, environment strip with each crewmember's cabin CO2 and a 3 mmHg limit line. Cards link to /crew/:id.
```

## Step 3 — Astronaut Detail (45 min)
```
Build the Astronaut Detail page (docs/PRD.md section 4.2): status banner with health score gauge and disclaimer,
"What to do now" checklist grouped by who (You / Crew / CMO / Ground) with RED first, alerts with rule/model badges,
vitals grid with baseline and delta, 72 h charts with abnormal hours shaded from /timeline and sleep/exercise
markers, "Why" panel from drivers, condition probability bars, and the daily plan.
```

## Step 4 — Long-term risk tab (25 min)
```
Add the Long-term risk tab (docs/PRD.md section 4.3): bone and muscle cards and projection chart from /forecast
(median + q10-q90 band + "if ARED target met"), and a radiation gauge from /radiation with SPE banner.
```

## Step 5 — Mission replay (25 min)
```
Add the replay slider to the header (docs/PRD.md section 4.4). Store `at` in a global store and in the URL query
string, include it in every query key, and add play/pause (1 hour per second). Add the quick-jump buttons
from the table in docs/PRD.md section 4.4 (exact timestamps are listed there).
```

## Step 6 — Alerts feed + polish (20 min)
```
Add /alerts (docs/PRD.md section 4.5). Then polish: loading skeletons, empty and error states, keyboard focus,
responsive layout down to 900 px, and a footer saying the data is synthetic and the app is decision support.
```

## Step 6b: Challenge extras
```
Add the items marked missing in docs/CHALLENGE.md: a clickable human body figure (heart, lungs, brain, bones/muscles,
blood, immune) colored by status; a measurement check-in form (BP, glucose, temperature, mood, sleep) that posts to
/api/assess; indicator explainer cards (why measure it, how space hazards affect it, when to escalate, prevention);
"due now" measurement reminders; and a data-source badge (real dataset vs simulated) on every value.
```

## Step 7 — Verify (10 min)
```
Run /verify. Then walk through the acceptance criteria in docs/PRD.md, take screenshots of each screen, and list
anything that is not done.
```

## Optional stretch
- **"Ask Sol" panel:** send the assessment JSON to an LLM and show a plain-language explanation in Arabic or English. Keep the structured assessment as the source of truth.
- **What-if form:** edit a few vitals and POST to `/api/assess` to show how the status changes.
- **Ground summary export:** one-page PDF/print view per astronaut for the next comm pass.
