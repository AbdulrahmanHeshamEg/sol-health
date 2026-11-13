# Datasets

The team agreed on these sources in the "Astra Health: data and models" doc. NASA has no public dataset of daily astronaut
vitals, so **real data calibrates a crew generator, and the engine runs on the generated crew**:

| Data | Source | What it stands for | Models it feeds |
|---|---|---|---|
| **PMData** | Simula (16 people, ~5 months, Fitbit Versa 2 + PMSys app) | The astronaut's body: HR, sleep, mood, fatigue | Personal baseline + CUSUM + Isolation Forest; deconditioning |
| **MSL RAD** | NASA / JPL, Curiosity rover | Radiation on the Mars surface | Cumulative dose counter + SPE spike detection |
| **OSDR EDA** | NASA Ames, ISS cabin during Rodent Research missions | Cabin air: CO2, temperature, humidity; ISS radiation | Rolling averages + environmental gate; CO2 generator |
| Published figures | Clinical ranges and papers | BP, SpO2, temperature, glucose (in no real dataset) | Generator only |

Every model is statistical and explainable. There is no deep learning and there are no real medical labels to train on.
Every alert must state its reason in one sentence.

Download everything with `data/fetch/` (see the README section "Get the data"). Raw files go to `data/raw/`, which is **git-ignored**.

---

## 1. PMData: the astronaut's body
- **Get:** `python data/fetch/fetch_pmdata.py` downloads from the Hugging Face mirror `aai530-group6/pmdata`. The original is at https://datasets.simula.no/pmdata/.
- **Layout:** `p01 … p16/` + `participant-overview.xlsx`. Each person has `fitbit/` (JSON + `sleep_score.csv`), `pmsys/` (`wellness.csv`, `injury.csv`, `srpe.csv`) and `googledocs/` (`reporting.csv`).
- **License:** ⚠️ **the sources disagree.** Simula's page says CC BY 4.0; the Hugging Face card's license file says CC BY-NC 4.0. Both are fine for a non-commercial hackathon. Always cite: Thambawita et al., *PMData: A Sports Logging Dataset*, MMSys 2020, doi:10.1145/3339825.3394926.

| File | Content | Frequency | Use? |
|---|---|---|---|
| `resting_heart_rate.json` | resting HR | daily | **Yes, the main indicator** |
| `heart_rate.json` | bpm | per few seconds | Yes, aggregate to hourly mean (large file, stream it) |
| `sleep.json` | light / deep / REM / awake time | per night | Yes |
| `sleep_score.csv` | score 0–100, deep sleep, restlessness, resting HR | per night | Yes |
| `wellness.csv` | fatigue, mood, readiness (0–10), sleep hours, sleep quality, soreness, stress (mostly 1–5, 3 = normal) | ~daily | **Yes, this replaces the daily check-in** (covers the challenge's *mood* and *sleep hours*) |
| `steps`, `*_active_minutes` | activity | per minute / daily | Optional, as context |
| `exercise.json` | session type, duration, HR | per session | Yes, for deconditioning |
| `injury.csv` | injury date, location, severity | per event | **Exclude these days** when counting false alarms (they are real changes) |
| `srpe.csv`, `reporting.csv`, food images | training load, meals, weight, water | — | No (only if time allows) |

**Limits:** healthy athletes on Earth. There is no BP, body temperature, SpO2 or glucose, and no medical events, so **every red alert on PMData counts as a false alarm.**

## 2. MSL RAD: radiation on the Mars surface
- **Get:** `python data/fetch/fetch_msl_rad.py 2024 2026` downloads daily level-2 CDF files from CDAWeb (`…/sp_phys/data/msl/rad/cdf/obs-l2/<year>/`). The file version differs per day and some days exist twice, so the script keeps the highest version. The 2026 folder held 316 files (to day 315) when checked on 13 Nov 2026. Backup source: the PDS PPI node.
- **Read:** `cdflib.CDF(path).cdf_info().zVariables`. **The variable names aren't known yet**: run `data/fetch/inspect_sources.py` first and record them here.

| Feature | Unit | Detector |
|---|---|---|
| Dose rate in silicon | µGy/day | RAD **B** |
| Dose rate in tissue-equivalent plastic | µGy/day | RAD **E**. **Start with this one**: it is closest to the human body |
| Timestamp per observation | — | — |

**Reference values for sanity checks**
- Surface, quiet Sun (Hassler et al. 2014, *Science*): tissue ≈ 0.21 mGy/day, silicon ≈ 0.16 mGy/day, dose equivalent ≈ 0.64 mSv/day, quality factor ≈ 3.0.
- Earth→Mars cruise (Zeitlin et al. 2013): ≈ 1.84 mSv/day. This is a fixed constant for the "in transit" setting, not from the CDF files.
- **Known event for validation:** 20 May 2024, the biggest surge RAD has measured since landing, about 8,100 µGy. The SPE detector **must** flag it, so download 2024.
- RAD shows a **daily (diurnal) cycle** on the surface, and the rover's RTG adds a constant background. Account for both in baselines.
- Converting Gy to Sv needs a quality factor. Use Q ≈ 3.0 from Hassler 2014 and say so in the UI.

## 3. OSDR EDA: cabin air on the ISS
- **Get:** `python data/fetch/fetch_osdr_eda.py` downloads every RR mission through the public EDA API (`https://visualization.osdr.nasa.gov/eda/api/missions/`) into `data/raw/osdr_eda/` as `RR-<n>_telemetry.csv` and `RR-<n>_radiation.csv`. The manual route in `data/fetch/OSDR_EDA_DOWNLOAD.md` gives the same tables.
- This is real ISS telemetry and **the dataset that sets Sol Health apart** from other entries.

| Feature | Frequency | Use |
|---|---|---|
| CO2 (ppm) | every 1 or 5 minutes | Environmental gate for headache / fatigue |
| Temperature | each time point | Context for sleep and body temperature |
| Relative humidity | each time point | Context only |
| GCR dose (excluding SAA) | daily | ISS-mode radiation |
| SAA dose | daily | ISS-mode radiation |
| Total and accumulated dose | daily | Cumulative dose counter |

**Confirmed from the files (13 Nov 2026):**
- **Columns.** Telemetry: `time` (UTC), `temperature_iss`, `temperature_ground` (°C), `humidity_iss`, `humidity_ground` (%), `co2_iss`, `co2_ground`, `milestones`. Radiation: `time`, `gcr`, `saa`, `total`, `milestones`.
- **CO2 unit is ppm**, not mmHg or %. Convert with `mmHg = ppm × 760 / 1e6` (1 atm cabin), so 3 mmHg ≈ 3,947 ppm and 2.5 mmHg ≈ 3,289 ppm.
- **Sampling interval:** 5 minutes for the older missions (RR-1, 3, 5, 6, 9, 12, 19), 1 minute for the newer ones (RR-18, 20, 23, 25, 28); RR-7 and RR-10 are irregular. Radiation is daily, in **mGy/day**. There is no accumulated-dose column: compute it as the running sum of `total`.
- **Coverage.** 14 RR missions have telemetry, 2014–2024. Longest: RR-18 (243 days), RR-20 (172), RR-7 (82), RR-5 (68), RR-25 (65), RR-6 (62).
- ⚠️ **RR-18, RR-20, RR-25 and RR-28 have no ISS CO2** (temperature and humidity only). The longest missions with CO2 are RR-7 (82 days, CO2 on about half the rows), RR-5 (68) and RR-6 (62).
- ⚠️ **Radiation is missing for RR-5, 10, 18, 20, 25 and 28.** RR-4, 8 and 17 have radiation but no telemetry. RR-22 is empty.
- ⚠️ **Median ISS CO2 is close to the limits**: 2,100–3,600 ppm per mission (1.6–2.8 mmHg), so the 2.5 mmHg 7-day rule will be exceeded for long stretches of the real series. Notebook 07 must report how often.
**Credit:** "Data and visualizations are courtesy of the Environmental Data Application (EDA) (https://visualization.osdr.nasa.gov/eda/)."

## 4. Published figures (generator only)
BP, SpO2, body temperature and blood glucose don't exist in any of the datasets above. The generator draws them from published
normal ranges, and they are labelled as simulated everywhere in the app.

## How it fits together
```
PMData ─┐ noise, autocorrelation, per-person variation
OSDR  ──┼──> Crew generator (+4 planted test cases) ──> Engine: baseline+CUSUM, Isolation Forest,
MSL RAD ┤ CO2 distribution, ISS dose / Mars dose        cabin gate + dose counter ──> GREEN / YELLOW / RED + reason
Papers ─┘ BP, SpO2, temp, glucose ranges
```

## Success is measured with two numbers
1. **False alarms per person per month** on real PMData (injury days excluded).
2. **Detection delay**: how many days after each planted case starts the system catches it.
