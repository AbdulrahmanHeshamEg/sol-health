"""Print what is actually inside the downloaded data, before any modelling.

    python data/fetch/inspect_sources.py

- MSL RAD: CDF zVariables (names, shapes, units) of the first file. The variable names for
  the dose rates (RAD B = silicon, RAD E = tissue-equivalent plastic) are NOT known yet; find them here.
- OSDR EDA: columns, dtypes, time range and apparent sampling rate of every CSV/XLSX in data/raw/osdr_eda/.
  Check whether CO2 is in % or mmHg (0.5 % = 3.8 mmHg at 1 atm).
- PMData: one participant's file heads.
"""
from pathlib import Path

import pandas as pd

RAW = Path(__file__).resolve().parents[2] / "data" / "raw"


def msl_rad():
    files = sorted((RAW / "msl_rad").rglob("*.cdf"))
    if not files:
        print("MSL RAD: no files. Run fetch_msl_rad.py"); return
    import cdflib
    cdf = cdflib.CDF(str(files[0]))
    info = cdf.cdf_info()
    print(f"\n=== MSL RAD: {files[0].name} ({len(files)} files) ===")
    for v in info.zVariables:
        vi = cdf.varinq(v)
        atts = cdf.varattsget(v)
        print(f"  {v:<40} dims={vi.Dim_Sizes} type={vi.Data_Type_Description} "
              f"units={atts.get('UNITS', '')} desc={str(atts.get('CATDESC', atts.get('FIELDNAM', '')))[:60]}")


def osdr_eda():
    files = sorted(p for p in (RAW / "osdr_eda").glob("*") if p.suffix.lower() in (".csv", ".xlsx", ".xls"))
    if not files:
        print("\nOSDR EDA: no files. See data/fetch/OSDR_EDA_DOWNLOAD.md"); return
    for f in files:
        df = pd.read_csv(f) if f.suffix.lower() == ".csv" else pd.read_excel(f)
        print(f"\n=== OSDR EDA: {f.name} shape={df.shape} ===")
        print(df.dtypes.to_string())
        print(df.head(3).to_string())
        tcol = next((c for c in df.columns if "time" in c.lower() or "date" in c.lower()), None)
        if tcol:
            t = pd.to_datetime(df[tcol], errors="coerce").dropna().sort_values()
            if len(t) > 2:
                print(f"time range {t.iloc[0]} -> {t.iloc[-1]}, median step {t.diff().median()}")


def pmdata():
    p = RAW / "pmdata" / "p01"
    if not p.exists():
        print("\nPMData: not found. Run fetch_pmdata.py"); return
    print("\n=== PMData p01 ===")
    for f in sorted(p.rglob("*")):
        if f.is_file():
            print(f"  {f.relative_to(p)}  {f.stat().st_size / 1e6:.1f} MB")
    for f in ("pmsys/wellness.csv", "fitbit/sleep_score.csv", "pmsys/injury.csv"):
        if (p / f).exists():
            print(f"\n{f}:\n{pd.read_csv(p / f).head(3).to_string()}")


if __name__ == "__main__":
    pmdata(); msl_rad(); osdr_eda()
