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

The app talks to one person, in the second person ("your heart", "your flight surgeon"). Navigation: Today · My body · Eye exam · Cabin ·
My doctor · Learn · Settings. The demo controls (which moment of the mission you see) live in Settings, not in the header.

### 4.1 Today (`/`)
- **Status:** greeting, status (colour + word + icon), the top alert and its one-sentence reason, health score.
- **Flight-surgeon card** (`escalation`): sent at once (RED, with arrival time), in tonight's report (YELLOW), or nothing to send.
- **What to do now:** actions grouped by who (You / Your flight surgeon on Earth), most urgent first.
- **Today's questions** (`/questions`): the engine's questions, grouped (the app needs to know · how you feel · morning tests · stool log ·
  vitals), each with "why we ask". Follow-ups appear when the engine needs them (CO2 high: headache? blood in urine: side pain?).
  Answers are saved on the device (`POST /answers`) and the engine re-assesses at once.
- **Your day** (`/daily-brief`): headline, what changed against last week, today's tips. Written by rules today; an AI model fills the same card later.
- **Your routine:** the daily plan and measurements due.

### 4.2 My body (`/body`)
Tabs: **Now** (clickable body figure with nine systems: heart, lungs, brain, eyes, immune, blood, kidneys, gut, bones and muscles; every alert
with its reason; every indicator against your normal with a real / simulated / entered badge; how the evidence splits), **Trends** (72 hours,
30 sols, including urine concentration and stool), **Long-term** (radiation dose, bone and muscle, fitness trend).

### 4.3 Eye exam (`/eyes`)
Latest fundus photo next to the baseline photo, the three measurements against baseline (disc edge sharpness, disc size, vessels visible at the
edge) with the limits from `/api/meta`, upload of any image (`POST /eye-photo`), and every photo of the mission.

### 4.4 Cabin (`/cabin`), My doctor (`/doctor`), Learn (`/learn`), Data and sources (`/about`)
Cabin CO2 and radiation; everything sent to the flight surgeon; explainer cards; data sources, citations and planted cases.

### 4.5 Settings (`/settings`): demo controls
The sol strip (one row, one column per sol), the jump-to buttons for each planted case, a sol slider and play (live mode); delete my entries;
connection status. While you look at an earlier moment, a strip on every page says so and offers "Back to now".

| Button | `at` | What judges see |
|---|---|---|
| A quiet day | `2026-09-15T12:00:00` | Clear, nothing sent |
| Cabin CO2 with headache reports | `2026-10-01T12:00:00` | Watch: likely environmental, ventilate first |
| Slow drift (illness onset) | `2026-10-16T12:00:00` | Watch: resting heart rate drifting above your normal |
| Eye exam: optic disc swelling | `2026-10-29T12:00:00` | Watch: eye photo changed; follow-up question about vision |
| Odd combination | `2026-10-31T12:00:00` | Watch: mood, stress and sleep worse together |
| Solar storm | `2026-11-13T08:00:00` | Act now: go to the storm shelter; sent to the flight surgeon at 05:00 |

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
