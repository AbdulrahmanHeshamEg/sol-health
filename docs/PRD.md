# Product Requirements — Sol Health

## 1. Problem

On long missions beyond low Earth orbit, crews cannot rely on a flight surgeon answering in real time.
Astronauts already wear and use many sensors, but the data is scattered and raw. A crewmember needs one
place that says: *how am I, is something wrong, and what do I do about it* — and that keeps working
when the link to Earth is slow or down.

## 2. Users

| User | Need | Main screen |
|---|---|---|
| Astronaut | Know their own status and the next action, in seconds | Astronaut Detail → "What to do now" |
| Crew Medical Officer (CMO) | See the whole crew, triage, follow checklists | Crew Overview, Alerts feed |
| Flight surgeon (ground) | Review trends and long-term risk at the next comm pass | Detail charts, Long-term risk |
| Hackathon judge | Understand the value in 2 minutes | Overview + Replay |

## 3. User stories

1. As an astronaut, I open the app and see my status color, health score and the single most important thing to do now.
2. As an astronaut, I can see each vital next to *my own* baseline, not a population average.
3. As the CMO, I see all crew sorted worst-first and can open anyone's detail in one click.
4. As the CMO, every alert tells me where it came from (hard limit or model), its confidence, and the checklist to follow.
5. As the flight surgeon, I can scroll back through the mission (replay) and see when an episode started.
6. As anyone, I can see long-term risk: projected bone and muscle loss and radiation dose against the career limit, and what change would reduce it.

## 4. Screens

### 4.1 Crew Overview (`/`)
- **Mission header:** mission name, `mission day X / planned_duration_days`, Earth comm delay, current time (`now`), replay slider (see 4.4).
- **Crew cards** (from `GET /api/crew`, already sorted worst-first): name, role, status chip (color + word + icon), health score (0–100), `condition_label`, `top_alert`, and HR, SpO2, core temp, BP.
- **Environment strip:** cabin CO2 per crewmember location (from each card's assessment context) with the 3 mmHg limit line.

### 4.2 Astronaut Detail (`/crew/:id`)
Data: `/assessment`, `/vitals?hours=72`, `/timeline?hours=72`.
- **Status banner:** status, `condition_label`, health score gauge, anomaly score, timestamp, disclaimer.
- **What to do now:** `actions[]` as a checklist, RED first, grouped by `who` (You / Crew / CMO / Ground). Checkboxes are local UI state only.
- **Alerts:** `alerts[]` with source badge (`rule` = hard clinical limit, `model` = statistical model, named in `alert.model`), the one-sentence `reason`, and the NASA hazard.
- **Vitals grid:** for each of 8 vitals and each daily indicator (`indicators`: resting HR, sleep hours, mood, stress, fatigue, blood glucose): value, unit, baseline, delta with arrow, and a **source badge** (real dataset vs simulated); highlight if an alert references that signal.
- **Charts (72 h):** HR, SpO2, core temp, systolic/diastolic BP, resp rate, HRV, PVT. Shade hours where timeline `p_abnormal > 0.5`, colored by condition. Mark sleep hours (`is_asleep`) and exercise hours (`exercise_type`).
- **Why:** `drivers[]` — "Respiration +3.8 br/min above your baseline" etc.
- **Evidence by condition:** horizontal bars from `probabilities` (relative evidence, not calibrated probabilities).
- **Body figure:** `body_systems[]` (heart, lungs, brain, bones/muscles, blood, immune), each clickable, colored by status, showing its function and summary.
- **Check-in form:** BP, glucose, temperature, mood, stress, fatigue, sleep, headache → `POST /api/assess` with `checkin`; show the returned assessment.
- **Reminders:** `/reminders` items that are due now, and the check-in streak.
- **Indicator explainer cards:** `/api/indicators` (why measure it, how space affects it, when to escalate, prevention).
- **Daily plan:** `daily_plan[]` (sleep, hydration, exercise targets).

### 4.3 Long-term risk (tab in detail)
Data: `/forecast?horizon_days=90`, `/radiation`.
- **Bone (hip BMD) and muscle (thigh) cards:** loss to date, projected loss at horizon (median + q10–q90), and *"if ARED target met"* value; alert badge when `hip_bmd.alert` is true (projected loss ≥ 5 %).
- **Chart:** cumulative projected loss vs mission day — current trajectory (band) vs target trajectory.
- **Radiation gauge:** `career_used_pct` of 600 mSv, projected % at mission end, dose rate, SPE banner if `spe_in_progress`.

### 4.4 Mission replay
A slider (hour resolution) between `time_range.start + 3 days` and `time_range.end` from `/api/mission`.
Changing it re-queries every endpoint with `at=<ISO timestamp>`. Play/pause button advances 1 hour per second.
Quick-jump buttons (verified against the demo data):

| Button | `at` | What judges see |
|---|---|---|
| A quiet day | `2026-09-20T12:00:00` | Whole crew GREEN |
| Cabin CO2 | `2026-10-01T12:00:00` | Nadia YELLOW: "likely environmental", ventilation first; cabin CO2 7-day mean above 2.5 mmHg for everyone |
| Slow drift | `2026-10-19T12:00:00` | Karim YELLOW: resting heart rate drifting above his own normal (CUSUM) |
| Odd combination | `2026-11-03T12:00:00` | Sofia: mood, stress and sleep worse together; low-mood rule on day 5 |
| Solar storm | `2026-11-13T08:00:00` | Whole crew RED: "SPE in progress: whole crew to the storm shelter" |
| Now | (no `at`) | Storm still under way, 19 hours in |

The marks come from `GET /api/mission → replay_marks` (case starts) and `data/demo/api_snapshots/replay_marks.json` (the moments saved for mock mode).

### 4.5 Alerts feed (`/alerts`)
All alerts across crew from each assessment, worst first, with astronaut name and link.

## 5. Non-functional requirements
- Works offline (mock mode from `data/demo/api_snapshots/`).
- Readable at arm's length: vitals ≥ 28 px, status visible from across a room.
- Color is never the only signal (word + icon).
- Every screen shows that data is synthetic and the app is decision support.
- p95 API response < 300 ms on a laptop (current engine ≈ 30–60 ms per assessment).

## 6. Out of scope (hackathon)
Real sensor integration, authentication, multi-mission storage, diagnosis, drug dosing.

## 7. Acceptance criteria
- Overview shows every crewmember with status, score, condition and top alert; clicking opens the detail page.
- Detail page shows actions, every indicator against the personal baseline, charts, and a one-sentence reason per alert.
- Each value carries a source badge (real dataset vs simulated).
- The replay slider shows each planted case (from `data/demo/planted_cases.json`) appearing and being caught.
- Works with the API stopped (mock mode). `pytest` green, `npm run build` clean, no console errors.

(The quick-jump table in 4.4 was refreshed after notebook 08 regenerated the demo crew.)
