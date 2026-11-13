import numpy as np
import pandas as pd
import pytest

from sol_ml.data import msl_rad


def frame(times, dose_e, flag=None):
    n = len(times)
    return pd.DataFrame({"time": pd.to_datetime(times), "dose_b": np.asarray(dose_e, float) * 1.05,
                         "dose_b_rtg": np.asarray(dose_e, float) * 0.7, "dose_e": np.asarray(dose_e, float),
                         "flag": flag or [""] * n, "alive_s": [930.0] * n})


def test_fill_values_become_missing():
    df = msl_rad.clean(frame(["2024-01-01 00:10", "2024-01-01 00:27"], [180.0, -1e31]))
    assert df["dose_e"].tolist()[0] == 180 and np.isnan(df["dose_e"].iloc[1])


def test_flagged_observations_are_marked_not_good():
    df = msl_rad.clean(frame(["2024-01-01 00:10", "2024-01-01 00:27"], [180.0, 185.0], flag=["", "Cmds"]))
    assert df["good"].tolist() == [True, False]


def test_mars_local_time_at_curiosity_landing_is_mid_afternoon():
    # Curiosity landed on 2012-08-06 05:17:57 UTC, about 15:00 local mean solar time at Gale crater.
    hour = msl_rad.mars_local_hour(pd.to_datetime(["2012-08-06 05:17:57"]))[0]
    assert hour == pytest.approx(15.0, abs=0.3)


def test_mars_local_time_advances_24_hours_in_one_sol():
    sol = pd.Timedelta(seconds=88775.244)
    t = pd.to_datetime(["2024-05-20 00:00:00"])
    a, b = msl_rad.mars_local_hour(t)[0], msl_rad.mars_local_hour(t + sol / 2)[0]
    assert (b - a) % 24 == pytest.approx(12.0, abs=0.01)


def test_hourly_table_averages_good_observations_and_keeps_empty_hours_missing():
    df = msl_rad.clean(frame(["2024-01-01 00:10", "2024-01-01 00:40", "2024-01-01 02:10", "2024-01-01 02:20"],
                             [100.0, 200.0, 300.0, 999.0], flag=["", "", "", "Cmds"]))
    h = msl_rad.to_hourly(df)
    assert h.loc[pd.Timestamp("2024-01-01 00:00"), "dose_e"] == 150
    assert h.loc[pd.Timestamp("2024-01-01 00:00"), "n"] == 2
    assert np.isnan(h.loc[pd.Timestamp("2024-01-01 01:00"), "dose_e"])
    assert h.loc[pd.Timestamp("2024-01-01 02:00"), "dose_e"] == 300          # the flagged 999 is ignored
    assert "local_hour" in h.columns


def test_daily_table_reports_mean_peak_and_coverage():
    times = pd.date_range("2024-01-01", periods=48, freq="30min")
    df = msl_rad.clean(frame(times, [200.0] * 47 + [800.0]))
    d = msl_rad.to_daily(df)
    row = d.loc[pd.Timestamp("2024-01-01")]
    assert row["dose_e"] == pytest.approx(200 + 600 / 24 / 2, rel=0.01)       # mean of the hourly means
    assert row["dose_e_max"] == 800 and row["hours"] == 24
