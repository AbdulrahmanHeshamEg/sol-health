# Model Cards

> **Status: v2, the models chosen in notebooks 02–09.** Every model is statistical and explainable; there is no deep learning.
> Parameters live in `models/engine_config.json` (written by the notebooks) and the engine reads them from there.
> The v0 prototype (a classifier trained on simulated labels) is kept as a baseline in `ml/sol_ml/engine_v0.py`; see the last section.

Reproduce everything: run notebooks `00` → `09` headless (`python notebooks/_src/make.py 00 01 ... 09`), then
`cd ml && python -m sol_ml.train_body` (fits the pooled Isolation Forest, about 1 s).

> **What the numbers mean.** False alarms are counted on **real people** (PMData: healthy athletes on Earth, no medical events,
> so every alert is false). Detection is measured on **changes we planted** into real series. Nothing here is sensitivity to real illness.

## The two success numbers

| | Result |
|---|---|
| **False alarms per person per month on real PMData** (body engine as shipped) | **1.00** (target ≤ 1), with 17 % of days spent in alert |
| **Detection delay on planted cases** | HR drift: 74 % caught, median 6 days · multi-signal drift: 87 %, 5 days · odd combination: 53 %, 2 days · sleep step: 45 %, 2 days |
| Solar storm of 20 May 2024 (real MSL RAD) | caught in its first hour; 0 unconfirmed alarms in 35 months |
| Planted cases on the generated astronaut | 4 of 4 caught by the part built for each (one example of each, so this shows the wiring, not a hit rate) |

## 1. Body: "is today abnormal for *this* person?" (notebook 02, re-tuned in 09)

Daily signals: resting HR, sleep minutes, fatigue, mood, stress. All are turned into **badness** units (positive = worse; PMSys self-reports are 5 = best).
Each day is compared with the person's own previous days: `z = (x − median) / (1.4826·MAD)`. For the 1–5 self-reports the MAD is usually 0,
so their scale is `1.2533 × mean absolute deviation` with a floor of half a scale point.

| Member | What it catches | Setting |
|---|---|---|
| **B. Personal robust z** | a single extreme day | 14-day window, alert at z > 5 in the unhealthy direction |
| **C. Bounded CUSUM** on z of resting HR, sleep, fatigue | slow drifts | 28-day window, k = 1, h = 5; each day's z clipped to ±4, sum capped at 8 |
| **E. Isolation Forest** on the 5-signal z-vector | odd combinations | pooled across people in z-space, flags the most isolated 5 % of training days, only when the day is on the unhealthy side |
| Low-mood rule | several low days in a row | mood ≤ 2 for 5 consecutive days |

Compared and rejected (notebook 02): population z-score (catches 0 of 200 personal HR drifts), EWMA (best single model, slower in combination),
robust Mahalanobis and LOF (weaker than the forest on odd combinations), per-person rolling multivariate models (no better, 20× slower).

Why the limits are not the textbook ones: personal z-scores have heavy tails on real data (4.1 % of real resting-HR days exceed z = 3; a normal
distribution gives 0.13 %), and resting HR is strongly autocorrelated (0.83 day to day). "Alert at |z| > 3" alone gives 1.6–3.0 false alarms per person-month.

File: `models/body_iforest.joblib` (forest, threshold, sorted training scores; trained on 1,425 real person-days). `anomaly_score` in the API
is the share of real training days that were *less* isolated than today.

**Limits.** Half of the subtle planted cases are missed at the 1-false-alarm target. 6 of 14 real people exceed 1 false alarm per month.
A CUSUM alarm, once on, lasts for days.

## 2. Fitness: "is the same exercise costing more heartbeats?" (notebook 03)

Weekly median heart rate per exercise type, centred on that type's own median, then **PELT change-point detection**; alert when the latest
change point is an upward shift of **≥ 8 bpm** that began within 4 weeks. On real PMData sessions: 0.22 false alarms per person-month;
catches 94 % of planted +2 bpm/week rises (median 5 weeks) and 50 % of +1 bpm/week. Rejected: efficiency index (only 8 of 16 people have paced sessions),
linear mixed model (similar, harder to explain), Theil–Sen slope (quietest; the fallback).

**Limits.** 57 % of PMData sessions are auto-detected walks; session HR varies by 9.4 bpm within a person and type. Sparse data.

## 3. Radiation (notebooks 04–05)

- **Dose counter (deterministic):** `mSv = Σ daily absorbed dose (mGy) × Q`, Q = 3.0 (Hassler et al. 2014), against the 600 mSv career limit.
  YELLOW at 80 %, RED at 100 %. Real rates: ISS 0.29 mGy/day (OSDR EDA), Mars surface 0.16 mGy/day (MSL RAD detector E); transit 1.84 mSv/day (Zeitlin et al. 2013).
- **Storm (SPE) alarm:** hourly dose rate ÷ trailing 7-day median. **≥ 1.3× = radiation elevated (YELLOW), ≥ 2× = go to the storm shelter now (RED), sent to the flight surgeon at once.**
  On 35 months of real RAD data: the 20 May 2024 storm is caught in its first hour (20× normal), 6 smaller real events reach the elevated level
  (each confirmed by RAD's independent silicon detector), 0 unconfirmed alarms. 93 % of the storm's extra dose arrived after the alarm.
  Compared: robust z (works at z > 6), CUSUM (7 hours late), EWMA, change point (equal, slower). Removing the 3.4 % diurnal cycle did not help.

**Limits.** One large storm in the record. Q = 3.0 was measured on Mars and overstates ISS dose equivalent.

## 4. Cabin air (notebooks 06–07)

Rule-based **environmental gate** (NASA OCHMO-TB-004): CO2 is high when the 1-hour mean is above 3 mmHg or the 7-day mean is above 2.5 mmHg.
A headache or fatigue report while CO2 is high is labelled **"likely environmental"**, and the first action is ventilation.
Replayed on 468 days of real ISS CO2: high 25 % of the time overall, up to 73 % on a 2016 mission, never on the 2020–21 missions.
The 1-hour limit also remains a hard rule on its own; the 7-day rule alone is shown as context, not as an alarm.

## 5. Hard clinical limits (rules win over models)

SpO2, core temperature, blood pressure (outside exercise), resting heart rate, cabin CO2, fasting glucose: see `docs/CLINICAL_PROTOCOLS.md`.
These are standard thresholds; BP, SpO2, temperature and glucose exist in no real dataset here, so they were not evaluated on data.

## 6. Bone and muscle projection (unchanged from v0)

Quantile gradient boosting trained on a **simulated** cohort built from published loss rates (hip BMD ≈ 1–1.5 %/month without countermeasures).
It is a what-if calculator for exercise adherence, labelled as simulated in the API.

## Baseline: the v0 classifier (kept for comparison)

`HistGradientBoosting` on 33 hourly features, trained and tested on labels from our own simulator (macro F1 0.94 there).
Notebook 09: on its own simulated crew it catches 92 % of scripted abnormal hours and flags 0.3 % of normal ones; on the data-calibrated astronaut
it flags **85 % of all hours as abnormal** outside the planted cases, almost always as "sleep deprivation", because real hour-to-hour
heart-rate variation (SD 6.9 bpm) is far larger than its simulator assumed (3 bpm). It cannot run on PMData at all (it needs eight hourly vitals no real dataset has).
What did transfer: its fixed radiation threshold and the shared hard limits.

## Escalation to the flight surgeon
The astronaut is alone, so the engine decides what reaches Earth (`assessment.escalation`): a **RED** alert is sent at once and arrives after the
one-way communication delay (13 minutes in the demo); **YELLOW** alerts go in the daily report at 20:00; with no alert nothing is sent.
`/api/crew/{id}/reports` lists every episode that went to Earth. Hourly wearable limits are confirmed before they can escalate:
blood pressure is judged awake and at rest, and a resting heart rate of 100 bpm or more must hold for two hours in a row.

## How the outputs combine
1. Every active alert has a level; **status = the worst level**.
2. **Models alone raise YELLOW.** RED comes from hard limits and from a storm at or above the shelter level.
3. Each alert carries a one-sentence `reason` (signal, how far from normal, for how long), its `kind`, and the NASA hazard behind it.
4. `health_score = 100 − 22·(RED alerts) − 9·(YELLOW alerts) − 15·anomaly_score`, clipped to 0–100.
5. `probabilities` are relative evidence weights per condition (they sum to 1); they are not calibrated probabilities.
