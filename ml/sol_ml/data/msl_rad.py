"""MSL RAD (Curiosity) level-2 dosimetry: daily CDF files -> tidy observation, hourly and daily tables.

    from sol_ml.data import msl_rad
    obs = msl_rad.load_all()            # one row per RAD observation (about every 17 minutes)
    hourly, daily = msl_rad.to_hourly(obs), msl_rad.to_daily(obs)

REAL data: NASA/JPL, Hassler et al. Dose rates are in microgray per day (uGy/day):
dose_b = silicon detector B (includes the rover's RTG), dose_b_rtg = B with the RTG background removed,
dose_e = tissue-equivalent plastic detector E (closest to the human body).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path(__file__).resolve().parents[3] / "data" / "raw" / "msl_rad"
DOSE_COLUMNS = ["dose_b", "dose_b_rtg", "dose_e"]
FILL_BELOW = -1e30
SOL_SECONDS = 88775.244
GALE_EAST_LONGITUDE = 137.44
TT_MINUS_UTC = 69.184          # seconds, valid since 2017 (37 leap seconds + 32.184)


def read_cdf(path: Path) -> pd.DataFrame:
    """One daily file -> raw observation rows (fill values still in place; see `clean`)."""
    import cdflib

    cdf = cdflib.CDF(str(path))
    dose = np.asarray(cdf.varget("DOSIMETRY_TOTAL"), float).reshape(-1, 3)
    return pd.DataFrame({
        "time": pd.to_datetime(cdflib.cdfepoch.to_datetime(cdf.varget("EPOCH"))),
        "dose_b": dose[:, 0], "dose_b_rtg": dose[:, 1], "dose_e": dose[:, 2],
        "flag": [str(x).strip() for x in np.ravel(cdf.varget("FLAGGED_DATA"))],
        "alive_s": np.ravel(cdf.varget("ALIVE_TIME")).astype(float)})


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Fill values -> NaN, add `good` (no quality flag) and sort by time."""
    out = df.copy()
    out[DOSE_COLUMNS] = out[DOSE_COLUMNS].where(out[DOSE_COLUMNS] > FILL_BELOW)
    out["good"] = out["flag"].eq("")
    return out.sort_values("time").reset_index(drop=True)


def load_all(root: Path = RAW) -> pd.DataFrame:
    """Every downloaded day, cleaned. Unreadable files are skipped and listed in `.attrs["skipped"]`."""
    frames, skipped = [], []
    for path in sorted(Path(root).rglob("*.cdf")):
        try:
            frames.append(read_cdf(path))
        except Exception as exc:
            skipped.append(f"{path.name}: {exc}")
    out = clean(pd.concat(frames, ignore_index=True))
    out.attrs["skipped"] = skipped
    return out


def mars_local_hour(times) -> np.ndarray:
    """Local mean solar time (0-24 h) at Curiosity's site in Gale crater (Mars24 algorithm, Allison & McEwen 2000).
    A Mars day (sol) is 24 h 39.6 min, so the daily cycle drifts against Earth clocks and must be read in local time."""
    t = pd.DatetimeIndex(times)
    jd_utc = (t - pd.Timestamp("2000-01-01 12:00:00")) / pd.Timedelta(days=1) + 2451545.0
    jd_tt = np.asarray(jd_utc, float) + TT_MINUS_UTC / 86400.0
    mars_sol_date = (jd_tt - 2405522.0028779) / 1.0274912517
    coordinated_mars_time = (24.0 * mars_sol_date) % 24.0
    return (coordinated_mars_time + GALE_EAST_LONGITUDE / 15.0) % 24.0


def to_hourly(obs: pd.DataFrame) -> pd.DataFrame:
    """Hourly mean dose rate of the good observations on a complete hourly index (hours without data are NaN)."""
    good = obs[obs["good"]].set_index("time")
    hourly = good[DOSE_COLUMNS].resample("1h").mean()
    hourly["n"] = good["dose_e"].resample("1h").count()
    hourly.index.name = "hour"
    hourly["local_hour"] = mars_local_hour(hourly.index + pd.Timedelta(minutes=30))
    return hourly


def to_daily(obs: pd.DataFrame) -> pd.DataFrame:
    """Daily mean dose rate (mean of the hourly means, so busy storm hours do not dominate), daily peak and coverage."""
    hourly = to_hourly(obs)
    day = hourly.index.normalize()
    daily = hourly[DOSE_COLUMNS].groupby(day).mean()
    good = obs[obs["good"]].set_index("time")
    daily["dose_e_max"] = good["dose_e"].groupby(good.index.normalize()).max()
    daily["hours"] = hourly["dose_e"].notna().groupby(day).sum()
    daily["n"] = hourly["n"].groupby(day).sum()
    daily.index.name = "date"
    return daily
