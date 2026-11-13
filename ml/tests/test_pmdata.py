"""Loader tests on a tiny hand-written participant folder that mirrors the real PMData layout."""
import json

import numpy as np
import pandas as pd
import pytest

from sol_ml.data import pmdata


@pytest.fixture
def root(tmp_path):
    p = tmp_path / "p01"
    (p / "fitbit").mkdir(parents=True)
    (p / "pmsys").mkdir()
    fb = p / "fitbit"

    def dump(name, obj):
        (fb / f"{name}.json").write_text(json.dumps(obj))

    dump("resting_heart_rate", [
        {"dateTime": "2019-11-01 00:00:00", "value": {"date": "11/01/19", "value": 53.7, "error": 6.7}},
        {"dateTime": "2019-11-02 00:00:00", "value": {"date": None, "value": 0.0, "error": 0.0}},
        {"dateTime": "2019-11-03 00:00:00", "value": {"date": "11/03/19", "value": 55.0, "error": 6.7}},
    ])

    def night(date, asleep, deep, rem, main=True):
        return {"dateOfSleep": date, "minutesAsleep": asleep, "mainSleep": main,
                "levels": {"summary": {"deep": {"minutes": deep}, "rem": {"minutes": rem},
                                       "light": {"minutes": asleep - deep - rem}}}}
    dump("sleep", [night("2019-11-01", 400, 60, 80), night("2019-11-01", 30, 0, 0, main=False),
                   {"dateOfSleep": "2019-11-03", "minutesAsleep": 300, "mainSleep": True,
                    "levels": {"summary": {"asleep": {"minutes": 300}}}}])
    (fb / "sleep_score.csv").write_text(
        "timestamp,sleep_log_entry_id,overall_score,composition_score,revitalization_score,duration_score,"
        "deep_sleep_in_minutes,resting_heart_rate,restlessness\n"
        "2019-11-01T06:29:30Z,1,76,18,20,38,27,53,0.05\n"
        "2019-11-02T07:19:30Z,2,79,20,22,37,36,54,0.07\n")
    dump("steps", [{"dateTime": "2019-11-01 10:00:00", "value": "100"},
                   {"dateTime": "2019-11-01 10:01:00", "value": "50"},
                   {"dateTime": "2019-11-03 09:00:00", "value": "7"}])
    dump("very_active_minutes", [{"dateTime": "2019-11-01 00:00:00", "value": "20"}])
    dump("moderately_active_minutes", [{"dateTime": "2019-11-01 00:00:00", "value": "10"}])
    dump("exercise", [{"activityName": "Run", "startTime": "2019-11-01 14:56:32", "duration": 1800000,
                       "averageHeartRate": 150, "distance": 5.0}])
    dump("heart_rate", [
        {"dateTime": "2019-11-01 00:00:05", "value": {"bpm": 50, "confidence": 3}},
        {"dateTime": "2019-11-01 00:30:00", "value": {"bpm": 60, "confidence": 3}},
        {"dateTime": "2019-11-01 01:00:00", "value": {"bpm": 70, "confidence": 3}},
        {"dateTime": "2019-11-02 23:59:55", "value": {"bpm": 90, "confidence": 1}},
    ])
    (p / "pmsys" / "wellness.csv").write_text(
        "effective_time_frame,fatigue,mood,readiness,sleep_duration_h,sleep_quality,soreness,soreness_area,stress\n"
        "2019-11-01T08:31:40.751Z,2,3,5,6,3,2,[],3\n"
        "2019-11-01T20:00:00.000Z,4,2,5,6,3,2,[],3\n"
        "2019-11-03T08:00:00.000Z,3,3,8,7,3,3,[],4\n")
    (p / "pmsys" / "injury.csv").write_text(
        "effective_time_frame,injuries\n"
        "2019-11-01T06:39:48.428Z,{}\n"
        "2019-11-03T22:33:38.989Z,{'right_hand': 'minor'}\n")
    return tmp_path


def day(s):
    return pd.Timestamp(s)


def test_resting_hr_treats_zero_as_missing(root):
    s = pmdata.load_resting_hr(root / "p01")
    assert s[day("2019-11-01")] == pytest.approx(53.7)
    assert np.isnan(s[day("2019-11-02")])


def test_resting_hr_missing_file_gives_empty_series(root):
    (root / "p01" / "fitbit" / "resting_heart_rate.json").unlink()
    assert pmdata.load_resting_hr(root / "p01").empty


def test_sleep_uses_main_sleep_and_handles_nights_without_stages(root):
    sl = pmdata.load_sleep(root / "p01")
    assert sl.loc[day("2019-11-01"), "sleep_minutes"] == 400
    assert sl.loc[day("2019-11-01"), "deep_minutes"] == 60
    assert sl.loc[day("2019-11-01"), "rem_minutes"] == 80
    assert sl.loc[day("2019-11-03"), "sleep_minutes"] == 300
    assert np.isnan(sl.loc[day("2019-11-03"), "deep_minutes"])


def test_wellness_keeps_the_last_report_of_each_day(root):
    w = pmdata.load_wellness(root / "p01")
    assert w.loc[day("2019-11-01"), "fatigue"] == 4
    assert w.loc[day("2019-11-01"), "mood"] == 2
    assert w.loc[day("2019-11-03"), "stress"] == 4


def test_wellness_zero_on_a_one_to_five_scale_is_missing(root):
    path = root / "p01" / "pmsys" / "wellness.csv"
    path.write_text(path.read_text() + "2019-11-04T08:00:00.000Z,0,0,0,0,3,3,[],4\n")
    w = pmdata.load_wellness(root / "p01")
    row = w.loc[day("2019-11-04")]
    assert np.isnan(row["fatigue"]) and np.isnan(row["mood"]) and np.isnan(row["sleep_duration_h"])
    assert row["readiness"] == 0 and row["stress"] == 4      # readiness is a 0-10 scale, so 0 is valid


def test_injury_days_only_lists_reports_with_an_injury(root):
    assert pmdata.load_injury_days(root / "p01") == [day("2019-11-03")]


def test_injury_days_missing_file_gives_empty_list(root):
    (root / "p01" / "pmsys" / "injury.csv").unlink()
    assert pmdata.load_injury_days(root / "p01") == []


def test_hourly_hr_aggregates_mean_min_max_per_hour(root):
    h = pmdata.load_hourly_hr(root / "p01", chunk_bytes=64)   # tiny chunks: records straddle chunk borders
    first = h.loc[pd.Timestamp("2019-11-01 00:00")]
    assert (first["hr_mean"], first["hr_min"], first["hr_max"], first["n"]) == (55, 50, 60, 2)
    assert h.loc[pd.Timestamp("2019-11-01 01:00"), "hr_mean"] == 70
    assert h.loc[pd.Timestamp("2019-11-02 23:00"), "hr_max"] == 90
    assert len(h) == 3


def test_daily_table_has_one_row_per_calendar_day_with_all_columns(root):
    d = pmdata.build_daily(root / "p01")
    assert list(d.index) == [day("2019-11-01"), day("2019-11-02"), day("2019-11-03")]
    for col in pmdata.DAILY_COLUMNS:
        assert col in d.columns
    r = d.loc[day("2019-11-01")]
    assert r["steps"] == 150 and r["active_minutes"] == 30 and r["exercised"]
    assert r["sleep_score"] == 76 and r["restlessness"] == pytest.approx(0.05)
    assert not d.loc[day("2019-11-03"), "exercised"]
    assert d.loc[day("2019-11-03"), "injury"] and not r["injury"]
    assert np.isnan(d.loc[day("2019-11-02"), "fatigue"])


def test_daily_resting_hr_falls_back_to_sleep_score_value(root):
    d = pmdata.build_daily(root / "p01")
    assert d.loc[day("2019-11-02"), "resting_hr"] == 54      # Fitbit value was 0 -> nightly value used
    assert d.loc[day("2019-11-01"), "resting_hr"] == pytest.approx(53.7)


def test_build_all_stacks_participants(root):
    (root / "p02").mkdir()
    for sub in ("fitbit", "pmsys"):
        (root / "p02" / sub).mkdir()
    (root / "p02" / "pmsys" / "wellness.csv").write_text(
        (root / "p01" / "pmsys" / "wellness.csv").read_text())
    allp = pmdata.build_all_daily(root)
    assert set(allp["person"]) == {"p01", "p02"}
    assert {"person", "date"} <= set(allp.columns)
