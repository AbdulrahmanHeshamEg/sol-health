# The NASA challenge, and how Sol Health answers it

**Challenge:** *Create Health Monitoring Software for Astronauts on Space Missions*. NASA Space Apps 2026, Intermediate level.
Tags: Human Exploration, Software, Space Exploration.

> Official one-line objective: *"Your challenge is to build a health monitoring software that gathers health
> indicators and enables astronauts to evaluate and act on the status of their health."*

Source for the summary below: the challenge statement as mirrored by a local Space Apps event page
(the official spaceappschallenge.org page blocks automated reading). The challenge's **data and resources were
released on Friday 13 Nov 2026**. See "Official resources" below.

## What the statement says (summarised)

**Background**
- Longer missions (Artemis, future Mars) mean more hazards and more physical and mental health risk.
- NASA's Human Research Program names five hazards (**RIDGE**): space **R**adiation, **I**solation and confinement,
  **D**istance from Earth, altered **G**ravity fields, and hostile closed **E**nvironments.
- These can cause immune changes, bone density loss, cardiovascular events, poor nutrition and behavioral health problems.
- Astronauts need to assess their own health. Example indicators: **blood pressure, heart rate, blood sugar,
  body temperature, daily sleep hours, mood**.

**Objectives**
1. A **visual tool** that lets astronauts assess their own health and gives **guidance on treatment and improvement**.
2. Input can be **keyboard text, mouse clicks, camera images** or other sources, as long as it is a health indicator
   (e.g. blood sugar in mg/dL, an ultrasound image).
3. Think through, per indicator: can it be measured in space, why is the exam needed, how do the hazards affect it,
   when does a result need the crew or the flight surgeon, and what actions prevent serious conditions.
4. **Strong interface design**: animation and interactivity, e.g. a **clickable human figure** that shows each body
   part's function and health status.

**Optional considerations**
1. Insights for different settings: spacecraft, space station, rover, planetary base.
2. Prompt astronauts to take measurements or complete actions as part of their routine.
3. Gamification of health tasks, dynamic charts over time, color-coded status.
4. Simple instructions and explanations of measurements, indicators and risks.

## Coverage check (what we have vs what the statement asks)

| Requirement | Status in Sol Health | What to add |
|---|---|---|
| Gather indicators: BP, HR, temperature | ✅ hourly telemetry | — |
| Blood sugar | ❌ missing | Add `blood_glucose_mg_dl` (fasting, 1–2×/day, manual entry) to data, features, rules, UI |
| Daily sleep hours | ⚠️ derived from `is_asleep` | **Real data: PMData `sleep.json` / `wellness.csv`**; show as a daily metric with an 8 h target |
| Mood | ❌ missing | **Real data: PMData `wellness.csv`** (mood, stress, fatigue, 1–5). Same scale for the in-app check-in |
| Evaluate status | ✅ rules + 3 ML models, GREEN/YELLOW/RED | — |
| Act: treatment / improvement guidance | ✅ action checklists + daily plan | — |
| Keyboard / click input | ❌ data only comes from the simulator | Manual **check-in form** → `POST /api/assess` |
| Camera input | ❌ | Stretch: photo of a meter or a skin issue, just stored and shown |
| Per-indicator explanation (why, hazard effect, when to escalate, prevention) | ⚠️ in docs only | **Indicator explainer cards** in the UI, driven by an `indicators.json` |
| Clickable human figure | ❌ | Body map: heart, lungs, brain, bones/muscles, blood, immune; color = status |
| Settings: spacecraft / station / rover / base | ❌ | Mission-setting selector that changes radiation rate, comm delay, available equipment |
| Prompts to measure | ❌ | "Due now" reminders from a measurement schedule |
| Gamification | ❌ | Streaks for check-ins, hydration and exercise targets |
| Charts over time, color coding | ✅ planned in PRD | — |
| RIDGE framing | ⚠️ partial | Tag each indicator and alert with its RIDGE hazard |

The ❌ and ⚠️ items are the to-do list. Most are frontend plus small engine additions. Mood and sleep come from real PMData. Blood sugar is in no
real dataset we have, so it is simulated from published ranges and labelled as simulated.

## Official resources (from the challenge page, released 13 Nov)
The official list contains **background reading, not datasets**. That is why the team picked its own real data (`docs/DATASETS.md`).
- **NASA:** *5 Hazards of Human Spaceflight* and *Risks of Human Spaceflight* (Human Research Program basics, with links to
  detailed reports), and *Ongoing HRP Research in Space*.
- **CSA (Canadian Space Agency):** *Monitoring Radiation for Astronaut Health* (Canadian radiation-measurement technology and
  research) and *Why Do We Conduct Science Experiments in Space?*

How to use them: tag each indicator and alert with its RIDGE hazard and HRP risk, and cite them in the indicator
explainer cards. The radiation module directly answers the CSA radiation resource.
