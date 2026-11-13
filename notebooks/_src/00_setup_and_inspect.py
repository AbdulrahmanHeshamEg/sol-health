# %% [markdown]
# # 00 · Setup and inspect the raw sources
#
# **Questions**
# 1. Did every download arrive, and how much of it?
# 2. What are the real variable names, units and sampling rates? (`docs/DATASETS.md` had them as "not confirmed".)
# 3. Is anything missing that changes the plan?
#
# **Inputs:** `data/raw/pmdata/`, `data/raw/msl_rad/`, `data/raw/osdr_eda/` (all real data, nothing simulated here).
# **Outputs:** the confirmed facts, written into `docs/DATASETS.md`. No processed tables yet.

# %%
import sys
sys.path.insert(0, "../ml")
import json
import cdflib
import numpy as np
import pandas as pd
from sol_ml.nbutil import *
from sol_ml.data import pmdata

rng = setup()
pd.set_option("display.width", 200)

# %% [markdown]
# ## 1. PMData (the astronaut's body)

# %%
people = pmdata.participants()
rows = []
for p in people:
    w = pmdata.load_wellness(p)
    rhr = pmdata.load_resting_hr(p).dropna()
    score = pmdata.load_sleep_score(p)
    rows.append({"person": p.name, "first_day": w.index.min().date(), "last_day": w.index.max().date(),
                 "wellness_days": len(w), "resting_hr_days": len(rhr), "sleep_score_nights": len(score),
                 "injury_file": (p / "pmsys" / "injury.csv").exists(),
                 "heart_rate_mb": round((p / "fitbit" / "heart_rate.json").stat().st_size / 1e6)})
pm = pd.DataFrame(rows).set_index("person")
print(f"{len(people)} participants, {pm.first_day.min()} to {pm.last_day.max()}")
pm

# %%
print((pmdata.RAW / "license.txt").read_text().split("\n")[0])
pd.read_csv(people[0] / "pmsys" / "wellness.csv").head(3)

# %% [markdown]
# ## 2. MSL RAD (radiation on the Mars surface)

# %%
cdf_files = sorted((RAW / "msl_rad").rglob("*.cdf"))
print(len(cdf_files), "daily CDF files:", {y.name: len(list(y.glob("*.cdf"))) for y in sorted((RAW / "msl_rad").iterdir())})
cdf = cdflib.CDF(str(cdf_files[0]))
pd.DataFrame([{"variable": v, "dims": cdf.varinq(v).Dim_Sizes, "units": cdf.varattsget(v).get("UNITS", ""),
               "description": str(cdf.varattsget(v).get("CATDESC", ""))[:70]} for v in cdf.cdf_info().zVariables])

# %%
labels = [str(x) for x in np.ravel(cdf.varget("DOSIMETRY_DOSE_LABEL"))[:3]]
t = pd.to_datetime(cdflib.cdfepoch.to_datetime(cdf.varget("EPOCH")))
dose = pd.DataFrame(cdf.varget("DOSIMETRY_TOTAL"), columns=labels, index=t)
print("dose columns:", labels)
print("observations in", cdf_files[0].name, ":", len(t), "| median step:", t.to_series().diff().median())
dose.describe().loc[["50%", "max"]].round(1)

# %% [markdown]
# ## 3. OSDR EDA (ISS cabin air and ISS radiation)

# %%
rows = []
for f in sorted((RAW / "osdr_eda").glob("*_telemetry.csv")):
    df = pd.read_csv(f, parse_dates=["time"])
    name = f.name.replace("_telemetry.csv", "")
    rad = RAW / "osdr_eda" / f"{name}_radiation.csv"
    co2 = df["co2_iss"].dropna()
    rows.append({"mission": name, "start": df.time.min().date(), "days": round((df.time.max() - df.time.min()).days),
                 "median_step": str(df.time.sort_values().diff().median()).replace("0 days ", ""),
                 "co2_iss_rows": len(co2), "co2_median_ppm": co2.median(),
                 "co2_median_mmHg": round(co2.median() * 760 / 1e6, 2) if len(co2) else None,
                 "radiation_days": len(pd.read_csv(rad)) if rad.exists() else 0})
eda = pd.DataFrame(rows).set_index("mission").sort_values("days", ascending=False)
eda

# %%
pd.read_csv(RAW / "osdr_eda" / "RR-1_radiation.csv").head(3)

# %% [markdown]
# ## Decision
#
# Nothing is modelled here; this notebook fixes the facts the other notebooks build on. All of them are now in `docs/DATASETS.md`.
#
# **Confirmed**
# - **PMData:** 16 participants, 1 Nov 2019 to 30 Mar 2020. Mirror license is CC BY-NC 4.0.
# - **MSL RAD:** dose rate is `DOSIMETRY_TOTAL` (µGy/day) with three columns: *Total Dose B* (silicon, includes the rover's RTG),
#   *RTG Corrected Dose B*, and *Total Dose E* (tissue-equivalent plastic). Time is `EPOCH`. Observations are irregular, roughly every 17 minutes.
# - **OSDR EDA:** CO2 is in **ppm** (not mmHg or %), so `mmHg = ppm × 760 / 1e6`. Sampling is every 5 minutes for the older missions
#   and every minute for the newer ones. Radiation is daily in mGy/day with `gcr`, `saa` and `total`.
#
# **What does not match the plan (said here and in chat, per the team rule)**
# 1. **Two people have no usable heart data.** p12 has one night of Fitbit data and p13 has 47. The body models will run on about 14 people, not 16.
# 2. **The longest ISS missions have no CO2.** RR-18 (243 days), RR-20, RR-25 and RR-28 carry temperature and humidity only.
#    CO2 work uses RR-7, RR-5, RR-6, RR-3, RR-1, RR-12, RR-10, RR-23, RR-19 and RR-9 (35–82 days each).
# 3. **Median ISS CO2 already sits near the team's limits** (1.6–2.8 mmHg per mission against limits of 2.5 and 3 mmHg).
#    The environmental gate will be active for long stretches of the real series; notebook 07 must quantify that before the thresholds are final.
# 4. **OSDR has no accumulated-dose column.** The dose counter sums `total` itself.
# 5. OSDR EDA was fetched through its public API (`data/fetch/fetch_osdr_eda.py`) instead of by hand. The tables are the same.
#
# **Known limits:** PMData people are healthy athletes on Earth, so it has no medical events and no BP, SpO2, temperature or glucose.
