# Clinical Thresholds and Action Protocols

> Decision support for a hackathon prototype. Thresholds are simplified from public references and common
> clinical practice; they are **not** medical advice. Onboard, the Crew Medical Officer and the flight
> surgeon make every medical decision. Source of truth in code: `ml/sol_ml/config.py` and `protocols.py`.

## Alert levels
| Level | Meaning | Who acts |
|---|---|---|
| GREEN | Within personal normal; follow daily plan | Astronaut |
| YELLOW | Something is drifting; act now, recheck soon | Astronaut, CMO informed |
| RED | Act immediately; stop safety-critical work; contact flight surgeon | Astronaut + CMO + ground |

## Hard limits (rules always override models)
| Signal | YELLOW | RED | Condition |
|---|---|---|---|
| SpO2 | < 94 % | < 90 % | hypoxia |
| Core temperature | ≥ 38.0 °C | ≥ 39.0 °C | fever_infection |
| Systolic BP | — | ≥ 160 mmHg | cardiovascular_strain |
| Systolic BP | — | < 90 mmHg | dehydration |
| Resting HR (activity < 0.2) | ≥ 100 bpm | ≥ 120 bpm | cardiovascular_strain |
| Local cabin ppCO2 | > 3 mmHg | > 6 mmHg | co2_exposure |

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
`who`: **self** = the astronaut, **crew** = any crewmember, **cmo** = Crew Medical Officer, **ground** = flight surgeon.
For RED, the RED actions come first, then the YELLOW actions.

### Sleep deprivation / fatigue
YELLOW: hand safety-critical tasks (EVA prep, robotics, docking) to a rested crewmate · 20–30 min nap if possible ·
protect next sleep window (dim lights, no screens, mask, earplugs) · repeat PVT after next sleep.
RED: stop safety-critical work, not cleared for EVA/robotics · CMO reviews sleep log and medications · notify flight surgeon.

### Dehydration
YELLOW: drink 500 ml now, then ~250 ml/h · electrolyte pouch in next 1 L · postpone exercise until HR is back to baseline · recheck in 2 h.
RED: stop and rest, oral rehydration now · CMO checks orthostatic symptoms, consider IV fluids per checklist · contact flight surgeon.

### Elevated CO2
YELLOW: move to a well-ventilated module, avoid poorly ventilated sleep stations · check fan and scrubber · report headache/blurred vision.
RED: leave and isolate the module until ppCO2 < 3 mmHg · scrubber off-nominal procedure, portable CO2 sweep · notify flight surgeon and ECLSS.

### Cardiovascular strain
YELLOW: stop exercise, rest seated 15 min · repeat BP/HR · avoid caffeine today.
RED: stop all activity, tell CMO · 12-lead ECG, chest-pain/arrhythmia checklist · contact flight surgeon with ECG.

### Fever / possible infection
YELLOW: rest, fluids, temperature every 2 h · mask, limit contact, clean shared surfaces · CMO logs symptoms, checks kit per checklist.
RED: CMO examines now, fever/infection checklist · isolate in separate sleep station · contact flight surgeon.

### Hypoxia
YELLOW: re-seat oximeter and repeat · check cabin ppO2 and total pressure · rest, slow breathing, report breathlessness.
RED: oxygen mask now · check for leak / O2 fault, emergency checklist · contact flight surgeon and ECLSS.

## Daily plan (shown even when GREEN)
Generated from the last 24 h / 7 days: sleep < 7 h, fluids < 80 % of 2.5 L, ARED or aerobic minutes < 85 % of weekly
target → one specific suggestion each; otherwise "all routine targets met".

## References
- NASA OCHMO Technical Brief OCHMO-TB-004, Carbon Dioxide; NASA-STD-3001 Vol. 2 Rev D [V2 6004].
- NASA OCHMO Radiation Protection Technical Brief; NASA-STD-3001 Vol. 1 [V1 4030], [V1 4031].
- National Academies (2021), *Space Radiation and Astronaut Health* — 600 mSv career limit recommendation.
- Lang et al. (2004), *J Bone Miner Res* — ISS hip bone loss; LeBlanc et al. (2000) Mir DXA data (~1–1.5 %/month).
