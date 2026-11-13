"""PMData loaders: one participant folder (p01 ... p16) -> tidy daily and hourly tables.

    from sol_ml.data import pmdata
    daily = pmdata.build_all_daily()            # person, date + DAILY_COLUMNS
    hourly = pmdata.load_hourly_hr(pmdata.RAW / "p01")

All values are REAL measurements from PMData (Thambawita et al., MMSys 2020). Days are calendar days of the
timestamps as stored (Fitbit local time; PMSys reports are UTC). A nightly sleep row belongs to its wake-up date.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path(__file__).resolve().parents[3] / "data" / "raw" / "pmdata"

WELLNESS_COLUMNS = ["fatigue", "mood", "readiness", "stress", "soreness", "sleep_quality", "sleep_duration_h"]
DAILY_COLUMNS = ["resting_hr", "sleep_minutes", "deep_minutes", "rem_minutes", "sleep_score", "restlessness",
                 "fatigue", "mood", "readiness", "stress", "soreness", "sleep_quality", "sleep_duration_h",
                 "steps", "active_minutes", "exercised", "injury"]

_HR_RECORD = re.compile(rb'"dateTime": "(\d{4}-\d\d-\d\d \d\d):\d\d:\d\d", "value": \{"bpm": (\d+)')
_HR_START = b'{"dateTime"'


def _json(path: Path) -> list:
    return json.loads(path.read_text()) if path.exists() else []


def _empty(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns, index=pd.DatetimeIndex([], name="date"), dtype=float)


def load_resting_hr(pdir: Path) -> pd.Series:
    """Daily resting HR (bpm). Fitbit writes 0 when it has no estimate; that becomes NaN."""
    rows = _json(pdir / "fitbit" / "resting_heart_rate.json")
    s = pd.Series({pd.Timestamp(r["dateTime"]).normalize(): float(r["value"]["value"]) for r in rows},
                  name="resting_hr", dtype=float)
    s.index = pd.DatetimeIndex(s.index, name="date")
    return s.replace(0.0, np.nan)


def load_sleep(pdir: Path) -> pd.DataFrame:
    """Main sleep per wake-up date: sleep_minutes, deep_minutes, rem_minutes (NaN for nights without stages)."""
    rows = []
    for r in _json(pdir / "fitbit" / "sleep.json"):
        if not r.get("mainSleep", True):
            continue
        summary = r.get("levels", {}).get("summary", {})
        rows.append({"date": pd.Timestamp(r["dateOfSleep"]), "sleep_minutes": float(r["minutesAsleep"]),
                     "deep_minutes": summary.get("deep", {}).get("minutes", np.nan),
                     "rem_minutes": summary.get("rem", {}).get("minutes", np.nan)})
    if not rows:
        return _empty(["sleep_minutes", "deep_minutes", "rem_minutes"])
    df = pd.DataFrame(rows).sort_values("sleep_minutes")
    return df.drop_duplicates("date", keep="last").set_index("date").sort_index().astype(float)


def load_sleep_score(pdir: Path) -> pd.DataFrame:
    """Nightly Fitbit sleep score, restlessness and the nightly resting HR, by wake-up date."""
    path = pdir / "fitbit" / "sleep_score.csv"
    cols = ["sleep_score", "restlessness", "resting_hr_night"]
    if not path.exists():
        return _empty(cols)
    df = pd.read_csv(path).rename(columns={"overall_score": "sleep_score", "resting_heart_rate": "resting_hr_night"})
    df["date"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(None).dt.normalize()
    return df.drop_duplicates("date", keep="last").set_index("date")[cols].sort_index().astype(float)


def load_wellness(pdir: Path) -> pd.DataFrame:
    """Self-reports (PMSys). If a person reports twice in a day, the last report wins.
    A 0 on a 1-5 scale or 0 hours slept is treated as missing; readiness is 0-10, so its 0 is kept."""
    path = pdir / "pmsys" / "wellness.csv"
    if not path.exists():
        return _empty(WELLNESS_COLUMNS)
    df = pd.read_csv(path)
    ts = pd.to_datetime(df["effective_time_frame"]).dt.tz_localize(None)
    df = df.assign(date=ts.dt.normalize(), _ts=ts).sort_values("_ts")
    out = df.drop_duplicates("date", keep="last").set_index("date")[WELLNESS_COLUMNS].astype(float)
    not_zero = [c for c in WELLNESS_COLUMNS if c != "readiness"]     # 1-5 scales and hours slept: 0 = not answered
    out[not_zero] = out[not_zero].replace(0.0, np.nan)
    return out


def load_injury_days(pdir: Path) -> list[pd.Timestamp]:
    """Calendar days on which the person reported at least one injury."""
    path = pdir / "pmsys" / "injury.csv"
    if not path.exists():
        return []
    df = pd.read_csv(path)
    hurt = df[df["injuries"].map(lambda s: bool(ast.literal_eval(s)) if isinstance(s, str) else False)]
    days = pd.to_datetime(hurt["effective_time_frame"]).dt.tz_localize(None).dt.normalize()
    return sorted(set(days))


def load_exercise(pdir: Path) -> pd.DataFrame:
    """Exercise sessions: start, date, activity, duration_min, avg_hr, distance, steps."""
    rows = [{"start": pd.Timestamp(r["startTime"]), "activity": r.get("activityName"),
             "duration_min": r.get("duration", np.nan) / 60000.0, "avg_hr": r.get("averageHeartRate", np.nan),
             "distance": r.get("distance", np.nan), "steps": r.get("steps", np.nan)}
            for r in _json(pdir / "fitbit" / "exercise.json")]
    df = pd.DataFrame(rows, columns=["start", "activity", "duration_min", "avg_hr", "distance", "steps"])
    df["date"] = pd.to_datetime(df["start"]).dt.normalize()
    return df.sort_values("start").reset_index(drop=True)


def _daily_sum(path: Path, name: str) -> pd.Series:
    rows = _json(path)
    if not rows:
        return pd.Series(name=name, dtype=float, index=pd.DatetimeIndex([], name="date"))
    df = pd.DataFrame(rows)
    out = pd.to_numeric(df["value"]).groupby(pd.to_datetime(df["dateTime"]).dt.normalize()).sum()
    return out.rename(name).rename_axis("date").astype(float)


def load_hourly_hr(pdir: Path, chunk_bytes: int = 16 << 20) -> pd.DataFrame:
    """Stream heart_rate.json (100+ MB) and aggregate to hourly hr_mean, hr_min, hr_max and sample count n."""
    path = pdir / "fitbit" / "heart_rate.json"
    parts, carry = [], b""

    def consume(buf: bytes):
        found = _HR_RECORD.findall(buf)
        if found:
            df = pd.DataFrame(found, columns=["hour", "bpm"])
            df["bpm"] = df["bpm"].astype(np.int64)
            parts.append(df.groupby("hour")["bpm"].agg(["sum", "count", "min", "max"]))

    if path.exists():
        with path.open("rb") as fh:
            while chunk := fh.read(chunk_bytes):
                buf = carry + chunk
                cut = buf.rfind(_HR_START)          # the last record may be cut off: keep it for the next chunk
                if cut <= 0:
                    carry = buf
                    continue
                consume(buf[:cut])
                carry = buf[cut:]
        consume(carry)
    if not parts:
        return pd.DataFrame(columns=["hr_mean", "hr_min", "hr_max", "n"], index=pd.DatetimeIndex([], name="hour"))
    agg = pd.concat(parts).groupby(level=0).agg({"sum": "sum", "count": "sum", "min": "min", "max": "max"})
    out = pd.DataFrame({"hr_mean": agg["sum"] / agg["count"], "hr_min": agg["min"], "hr_max": agg["max"],
                        "n": agg["count"]})
    out.index = pd.DatetimeIndex(pd.to_datetime([h.decode() for h in agg.index], format="%Y-%m-%d %H"), name="hour")
    return out.sort_index()


def build_daily(pdir: Path) -> pd.DataFrame:
    """One row per calendar day between the person's first and last record, with DAILY_COLUMNS."""
    fb = pdir / "fitbit"
    score = load_sleep_score(pdir)
    active = _daily_sum(fb / "very_active_minutes.json", "very").add(
        _daily_sum(fb / "moderately_active_minutes.json", "moderate"), fill_value=0).rename("active_minutes")
    parts = [load_resting_hr(pdir), load_sleep(pdir), score, load_wellness(pdir),
             _daily_sum(fb / "steps.json", "steps"), active]
    df = pd.concat(parts, axis=1).sort_index()
    if df.empty:
        return pd.DataFrame(columns=DAILY_COLUMNS, index=pd.DatetimeIndex([], name="date"))
    df = df.reindex(pd.date_range(df.index.min(), df.index.max(), name="date"))
    df["resting_hr"] = df["resting_hr"].fillna(df["resting_hr_night"])
    df["exercised"] = df.index.isin(load_exercise(pdir)["date"])
    df["injury"] = df.index.isin(load_injury_days(pdir))
    return df[DAILY_COLUMNS]


def participants(root: Path = RAW) -> list[Path]:
    return sorted(p for p in Path(root).glob("p[0-9][0-9]") if p.is_dir())


def build_all_daily(root: Path = RAW) -> pd.DataFrame:
    """Daily table for every participant, stacked: person, date + DAILY_COLUMNS."""
    frames = [build_daily(p).reset_index().assign(person=p.name) for p in participants(root)]
    return pd.concat(frames, ignore_index=True)[["person", "date", *DAILY_COLUMNS]]
