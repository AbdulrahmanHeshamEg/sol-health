# Clinical Thresholds and Action Protocols

> Decision support for a hackathon prototype. Thresholds are simplified from public references and common
> clinical practice; they are **not** medical advice. Onboard, the Crew Medical Officer and the flight
> surgeon make every medical decision. Source of truth in code: `ml/sol_ml/config.py` and `protocols.py`.

## Alert levels
| Level | Meaning | Who acts |
|---|---|---|
| GREEN | Within personal normal; follow daily plan | Astronaut |
| YELLOW | Something is drifting; act now, recheck soon | You; it goes in the daily report to your flight surgeon |
| RED | Act immediately; stop safety-critical work | You; sent to your flight surgeon at once |

## Hard limits (rules always override models)
| Signal | YELLOW | RED | Condition |
|---|---|---|---|
| SpO2 | < 94 % | < 90 % | hypoxia |
| Core temperature | ≥ 38.0 °C | ≥ 39.0 °C | fever_infection |
| Systolic BP (awake, at rest) | — | ≥ 160 mmHg | cardiovascular_strain |
| Systolic BP (awake, at rest) | — | < 90 mmHg | dehydration |
| Resting HR (activity < 0.2, two hours in a row) | ≥ 100 bpm | ≥ 120 bpm | cardiovascular_strain |
| Local cabin ppCO2 | > 3 mmHg | > 6 mmHg | co2_exposure |
| Fasting blood glucose | < 70 or ≥ 126 mg/dL | < 54 or ≥ 250 mg/dL | low_blood_sugar / high_blood_sugar |
| Mood score (1–5, 5 = best) | ≤ 2 for 5 days in a row | — | low_mood |

Glucose: below 70 mg/dL is hypoglycaemia and below 54 mg/dL is clinically significant hypoglycaemia; a fasting value of 126 mg/dL or more is the diabetes threshold.
The mood rule's 5 days is a team choice set in notebook 09 (the shortest rule that keeps false alarms on real people at 1 per person-month).

## Model alerts (YELLOW only; parameters from `models/engine_config.json`)
| Alert | Fires when | Condition |
|---|---|---|
| Unusual reading | a daily signal is more than 5 robust SD worse than the person's 14-day normal | acute_deviation |
| Slow drift | bounded CUSUM of resting HR, sleep or fatigue above 5 | physiological_drift |
| Unusual combination | Isolation Forest flags the day's 5-signal z-vector, on the unhealthy side | unusual_combination |
| Fitness trend | exercise heart rate shifted up by 8 bpm or more within 4 weeks | deconditioning |
| Likely environmental | CO2 high (1-hour > 3 or 7-day > 2.5 mmHg) with a headache or fatigue report | co2_exposure |
| Radiation elevated / storm shelter | dose rate ≥ 1.3× / ≥ 2× the 7-day normal (the 2× level is RED) | radiation_event |

CO2: NASA-STD-3001 Vol. 2 Rev D [V2 6004] limits the 1-hour average ppCO2 to ≤ 3 mmHg; NASA's CO2 technical brief
links headaches to 2.8–4.5 mmHg and fatigue, poor sleep and nausea to levels above 4.5 mmHg.

## Long-term limits
| Item | Limit | Source |
|---|---|---|
| Career radiation (effective dose) | 600 mSv, same for all ages and sexes | NASA-STD-3001 Vol. 1 [V1 4030] |
| Solar particle event | 250 mSv per event | NASA-STD-3001 Vol. 1 [V1 4031] |
| Projected hip BMD loss alert | ≥ 5 % at horizon | team choice; spaceflight losses of ~1–1.5 %/month reported |
| Resistive exercise target | 360 min/week (ARED) | team choice, mirrors ISS ~6 sessions/week |
| Aerobic target | 240 min/week | team choice |
| Sleep target | 8 h/day | team choice |
| Fluids | 2.5 L/day | team choice |

## Action checklists
`who`: **self** = you, the astronaut (alone on the mission); **ground** = your flight surgeon on Earth, reached with the communication delay.
There is no crewmate or crew medical officer, so steps that needed a second person are now yours (with the medical-kit checklist) or the flight surgeon's.
The full text of every checklist is in `ml/sol_ml/protocols.py`; the summaries below give the gist.
For RED, the RED actions come first, then the YELLOW actions.

### Sleep deprivation / fatigue
YELLOW: hand safety-critical tasks (EVA prep, robotics, docking) to a rested crewmate · 20–30 min nap if possible ·
protect next sleep window (dim lights, no screens, mask, earplugs) · repeat PVT after next sleep.
RED: stop safety-critical work, not cleared for EVA/robotics · sleep log and reaction-time trend sent to the flight surgeon.

### Dehydration
YELLOW: drink 500 ml now, then ~250 ml/h · electrolyte pouch in next 1 L · postpone exercise until HR is back to baseline · recheck in 2 h.
RED: stop and rest, oral rehydration now · check for dizziness on standing, dehydration checklist · flight surgeon notified, advises on IV fluids from the kit.

### Elevated CO2 / likely environmental
YELLOW: **increase ventilation first** (fan and scrubber check) · move to a well-ventilated module, avoid poorly ventilated sleep stations · check fan and scrubber · report headache/blurred vision.
RED: leave and isolate the module until ppCO2 < 3 mmHg · scrubber off-nominal procedure, portable CO2 sweep · notify flight surgeon and ECLSS.

### Cardiovascular strain
YELLOW: stop exercise, rest seated 15 min · repeat BP/HR · avoid caffeine today.
RED: stop all activity and rest · 12-lead ECG with the medical kit, chest-pain checklist · ECG and vitals sent to the flight surgeon.

### Fever / possible infection
YELLOW: rest, fluids, temperature every 2 h · log symptoms, antipyretic from the kit per checklist · clean surfaces and equipment you used.
RED: start the fever / infection checklist now · temperature trend and symptoms sent to the flight surgeon.

### Hypoxia
YELLOW: re-seat oximeter and repeat · check cabin ppO2 and total pressure · rest, slow breathing, report breathlessness.
RED: oxygen mask now · check for leak / O2 fault, emergency checklist · contact flight surgeon and ECLSS.

### Solar particle event
YELLOW (elevated): stop EVA preparation, check the storm shelter · keep dosimeters on, avoid thinly shielded areas · report at next comm pass.
RED (shelter): **go to the storm shelter now** · abort EVA or rover traverse · log your dosimeter on entering and leaving · flight surgeon notified, stay until the rate is below the elevated level.

### Slow drift / unusual reading / unusual combination / low mood / fitness trend / blood sugar
Each has a short YELLOW checklist in `ml/sol_ml/protocols.py`: repeat or complete the measurements, protect sleep and fluids, and the flight surgeon sees it in the daily report;
for mood and odd combinations a private conference with the flight surgeon is offered. Low blood sugar: 15 g of fast sugar, recheck in 15 minutes.

## Daily plan (shown even when GREEN)
Generated from the last 24 h / 7 days: sleep < 7 h, fluids < 80 % of 2.5 L, ARED or aerobic minutes < 85 % of weekly
target → one specific suggestion each; otherwise "all routine targets met".

## References
- NASA OCHMO Technical Brief OCHMO-TB-004, Carbon Dioxide; NASA-STD-3001 Vol. 2 Rev D [V2 6004].
- NASA OCHMO Radiation Protection Technical Brief; NASA-STD-3001 Vol. 1 [V1 4030], [V1 4031].
- National Academies (2021), *Space Radiation and Astronaut Health* — 600 mSv career limit recommendation.
- Lang et al. (2004), *J Bone Miner Res* — ISS hip bone loss; LeBlanc et al. (2000) Mir DXA data (~1–1.5 %/month).
