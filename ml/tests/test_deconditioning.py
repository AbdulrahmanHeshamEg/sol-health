import numpy as np
import pandas as pd
import pytest

from sol_ml.detectors import deconditioning as dc


def sessions(weeks=12, per_week=3, slope=0.0, seed=0, activities=("Run", "Walk"), noise=1.0):
    """Synthetic sessions: Run around 150 bpm, Walk around 100 bpm, optional bpm/week trend."""
    rng = np.random.default_rng(seed)
    level = {"Run": 150.0, "Walk": 100.0, "Treadmill": 140.0}
    rows = []
    for w in range(weeks):
        for a in activities:
            for _ in range(per_week):
                rows.append({"week": w, "activity": a, "avg_hr": level[a] + slope * w + rng.normal(0, noise),
                             "duration_min": 30.0, "distance": 5.0 if a != "Walk" else np.nan})
    return pd.DataFrame(rows)


def test_add_week_counts_whole_weeks_from_a_common_monday():
    df = pd.DataFrame({"start": pd.to_datetime(["2019-10-28 08:00", "2019-11-03 23:00", "2019-11-04 00:10"])})
    assert dc.add_week(df)["week"].tolist() == [0, 0, 1]


def test_centering_removes_the_level_difference_between_activity_types():
    weeks, hr = dc.centered_weekly(sessions(noise=0.0), lo=0, hi=11)
    assert len(weeks) == 24                                   # 12 weeks x 2 activity types, one weekly median each
    assert np.allclose(hr, 0.0)


def test_centering_ignores_activity_types_with_too_few_weeks():
    s = sessions(noise=0.0)
    s = pd.concat([s, pd.DataFrame([{"week": 5, "activity": "Treadmill", "avg_hr": 140.0, "duration_min": 30, "distance": 5}])])
    weeks, _ = dc.centered_weekly(s, lo=0, hi=11, min_weeks=3)
    assert len(weeks) == 24


def test_trend_stat_recovers_a_planted_slope_and_is_flat_otherwise():
    slope, low = dc.trend_stat(sessions(slope=2.0), week=11, lookback=8)
    assert slope == pytest.approx(2.0, abs=0.3) and low > 0
    slope, low = dc.trend_stat(sessions(slope=0.0), week=11, lookback=8)
    assert abs(slope) < 0.3 and low <= 0.2


def test_trend_stat_needs_enough_weeks():
    slope, low = dc.trend_stat(sessions(weeks=2), week=1, lookback=8)
    assert np.isnan(slope)


def test_inject_trend_raises_heart_rate_only_from_the_start_week():
    s = sessions(noise=0.0)
    out = dc.inject_trend(s, start_week=6, bpm_per_week=2.0)
    run = out[out.activity == "Run"].groupby("week").avg_hr.mean()
    assert run[5] == 150 and run[6] == 152 and run[9] == 158
    assert s.avg_hr.max() == 150                              # the input is not modified


def test_efficiency_stat_rises_when_the_same_pace_costs_more_heartbeats():
    fit = dc.efficiency_stat(sessions(slope=0.0, noise=0.2), week=11, lookback=8)[0]
    worse = dc.efficiency_stat(sessions(slope=3.0, noise=0.2), week=11, lookback=8)[0]
    assert abs(fit) < 0.3 and worse == pytest.approx(100 * 3.0 / 150, abs=0.5)     # percent per week


def test_efficiency_stat_is_nan_without_distance_sessions():
    assert np.isnan(dc.efficiency_stat(sessions(activities=("Walk",)), week=11, lookback=8)[0])


def test_changepoint_stat_reports_the_size_of_a_recent_upward_step():
    s = sessions(weeks=14, noise=0.5)
    s.loc[s.week >= 10, "avg_hr"] += 8.0
    shift, weeks_ago = dc.changepoint_stat(s, week=13, penalty=5.0)
    assert shift == pytest.approx(8.0, abs=1.5) and weeks_ago == 4
    shift, _ = dc.changepoint_stat(sessions(weeks=14, noise=0.5), week=13, penalty=5.0)
    assert shift == 0.0


def test_alert_weeks_need_a_slope_above_threshold_and_a_positive_lower_bound():
    stats = np.array([[2.0, 0.5], [2.0, -0.1], [0.4, 0.3], [np.nan, np.nan]])
    assert dc.alerts(stats, thr=1.0).tolist() == [True, False, False, False]


def test_weekly_false_alarm_rate_is_per_thirty_days():
    alerts = np.zeros(20, bool)
    alerts[[8, 9, 15]] = True
    mask = np.ones(20, bool)
    mask[:6] = False
    assert dc.false_alarm_rate([alerts], [mask]) == pytest.approx(2 / (14 * 7 / 30))
