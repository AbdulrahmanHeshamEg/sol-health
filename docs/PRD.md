# Product Requirements — Sol Health

## 1. Problem

On long missions beyond low Earth orbit, crews cannot rely on a flight surgeon answering in real time.
Astronauts already wear and use many sensors, but the data is scattered and raw. An astronaut needs one
place that says: *how am I, is something wrong, and what do I do about it* — and that keeps working
when the link to Earth is slow or down.

## 2. Users

| User | Need | Main screen |
|---|---|---|
| The astronaut (alone on the mission) | Know their own status and the next action, in seconds, and know the doctor is told | Me |
| Flight surgeon (Earth, 13 min away) | Receive what matters: act-now alerts at once, watch alerts in the daily report | Flight surgeon (what was sent) |
| Hackathon judge | Understand the value in 2 minutes | Me + the jump-to buttons |

The app is **personal**: one astronaut, one device. There is no crewmate or crew medical officer to hand work to, so every
action is either the astronaut's own or something that goes to the flight surgeon (team decision, 14 Nov 2026).

## 3. User stories

1. As the astronaut, I open the app and see my status, my health score and the single most important thing to do now.
2. As the astronaut, I see each indicator next to *my own* baseline, not a population average.
3. As the astronaut, every alert tells me what moved, how far from my normal, and for how long.
4. As the astronaut, I can see what has been sent to my flight surgeon and when it reaches Earth.
5. As the astronaut, I can enter a measurement (blood pressure, blood sugar, temperature, mood, sleep, headache) and see the engine's answer.
6. As the astronaut, I can check the cabin: CO2 and radiation, and whether a headache is probably the air.
7. As anyone, I can scroll back through the mission (replay) and see each planted case appear and be caught.

## 4. Screens

### 4.1 Me (`/`): the home page
Data: `/api/me`, `/assessment`, `/vitals?hours=72`, `/timeline?hours=72`, `/daily?days=30`, `/reminders`.
- **Status banner:** status (colour + word + icon), name, the top alert and its one-sentence reason, health score gauge, how unusual today is.
- **Flight-surgeon card** (`escalation`): "Sent to your flight surgeon" (RED, with sent and arrival time), "In tonight's report" (YELLOW) or "Nothing needs your flight surgeon"; the message text on request.
- **What to do now:** `actions[]` grouped by who (You / Your flight surgeon on Earth), most urgent first. Checkboxes are local only.
- **Your body:** clickable figure from `body_systems[]` (heart, lungs, brain, bones and muscles, blood, immune), each coloured by status, with its function and summary.
- **Why:** every alert with its reason, source (clinical limit or named statistical model) and NASA hazard.
- **Every indicator against your own normal:** daily indicators and hourly vitals, each with value, baseline, delta and a real / simulated badge.
- **Last 72 hours** and **last 30 sols** charts, with watch / act-now hours shaded and model-flagged days ringed.
- **Daily plan**, **measurements due** (with the check-in streak), and **how the evidence splits**.
- **Measurement check-in:** `POST /api/assess` with `checkin`; shows the engine's answer.
- **Long-term risk** tab: radiation dose against the career limit, bone and muscle projection, fitness trend.

### 4.2 Cabin (`/cabin`)
CO2 (1-hour and 7-day, against the limits from `/api/meta`), radiation against its 7-day normal, 72-hour charts of both, and the dose panel.
It is the habitat, not the body: when CO2 is high, a headache is probably the cabin.

### 4.3 Flight surgeon (`/reports`)
The current escalation and the list from `/reports`: every alert episode that went to Earth, newest first, with when it was sent,
when it arrived and what it said.

### 4.4 Mission replay
The sol strip in the header: one row, one column per sol, coloured by the worst status of that sol. A slider (live mode) or the
jump-to buttons move `at`; every query re-runs with `at=<ISO timestamp>`. Play advances 1 hour per second.

| Button | `at` | What judges see |
|---|---|---|
| A quiet day | `2026-09-15T12:00:00` | GREEN, nothing sent |
| Cabin CO2 with headache reports | `2026-10-01T12:00:00` | YELLOW: "likely environmental", ventilate first; in the daily report |
| Slow drift (illness onset) | `2026-10-16T12:00:00` | YELLOW: resting heart rate drifting above her own normal (CUSUM) |
| Odd combination | `2026-10-31T12:00:00` | YELLOW: mood, stress and sleep worse together (Isolation Forest) |
| Solar storm | `2026-11-13T08:00:00` | RED: go to the storm shelter now; sent to the flight surgeon at 05:00 |
| Now | (no `at`) | Storm still under way, 19 hours in |

### 4.5 What we measure (`/learn`) and Data and sources (`/about`)
Explainer cards from `/api/indicators`; data sources, citations, the planted cases and how the engine was checked.

## 5. Non-functional requirements
- Works offline (mock mode from `data/demo/api_snapshots/`).
- Readable at arm's length: vitals ≥ 28 px, status visible from across a room.
- Color is never the only signal (word + icon).
- Every screen shows that data is synthetic and the app is decision support.
- p95 API response < 300 ms on a laptop (current engine ≈ 30–60 ms per assessment).

## 6. Out of scope (hackathon)
Real sensor integration, authentication, multi-mission storage, diagnosis, drug dosing.

## 7. Acceptance criteria
- The home page shows the astronaut's status, score, top alert with its reason, and what has been sent to the flight surgeon.
- The home page shows actions (yours and the flight surgeon's), every indicator against the personal baseline, charts, and a one-sentence reason per alert.
- Each value carries a source badge (real dataset vs simulated).
- The replay slider shows each planted case (from `data/demo/planted_cases.json`) appearing and being caught.
- Works with the API stopped (mock mode). `pytest` green, `npm run build` clean, no console errors.

(The quick-jump table in 4.4 was refreshed after notebook 08 regenerated the demo crew.)
