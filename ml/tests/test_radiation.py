import numpy as np
import pytest

from sol_ml.detectors import radiation as rad

NAN = np.nan


def quiet(n=24 * 40, level=170.0, noise=4.0, seed=0):
    return level + np.random.default_rng(seed).normal(0, noise, n)


def test_trailing_baseline_uses_previous_hours_only_and_skips_gaps():
    x = np.array([10.0, NAN, 12.0, 14.0, 500.0])
    med, scale = rad.trailing_baseline(x, window=4, min_periods=3)
    assert np.isnan(med[2])                                   # only one earlier value
    assert med[4] == 12.0                                     # median of 10, 12, 14: the 500 is not in its own baseline
    assert scale[4] == pytest.approx(1.4826 * 2.0)


def test_robust_z_flags_a_storm_and_stays_quiet_otherwise():
    x = quiet()
    x[700:706] *= 10
    z = rad.spe_score(x, "robust_z")
    assert z[700] > 20
    assert (z[200:700] > 8).sum() == 0


def test_ratio_score_is_today_over_the_trailing_median():
    x = np.full(300, 100.0)
    x[250] = 250.0
    assert rad.spe_score(x, "ratio")[250] == pytest.approx(2.5)


def test_slow_solar_cycle_drift_is_absorbed_by_the_moving_baseline():
    n = 24 * 120
    x = quiet(n) * np.linspace(1.0, 1.3, n)                   # +30 % over four months
    for method, thr in (("robust_z", 8.0), ("ratio", 1.5)):
        assert not (rad.spe_score(x, method) > thr).any()


def test_cusum_and_ewma_on_log_dose_rise_under_a_sustained_increase():
    x = quiet()
    x[700:] *= 1.5
    for method in ("cusum", "ewma"):
        s = rad.spe_score(x, method)
        assert s[700:712].max() > 5 * np.nanmax(s[200:700])


def test_deseasonalize_removes_a_local_time_cycle():
    n = 24 * 60
    local_hour = (np.arange(n) * 24 / 24.66) % 24             # a sol is longer than a day
    x = 170 * (1 + 0.05 * np.sin(2 * np.pi * local_hour / 24))
    flat = rad.deseasonalize(x, local_hour)
    assert np.nanstd(flat[24 * 20:]) < 0.2 * np.std(x)
    assert np.nanmean(flat[24 * 20:]) == pytest.approx(170, rel=0.01)


def test_persistent_alerts_need_consecutive_hours():
    a = np.array([1, 0, 1, 1, 0, 1, 1, 1], bool)
    assert rad.persistent(a, 2).tolist() == [False, False, False, True, False, False, True, True]
    assert rad.persistent(a, 1).tolist() == a.tolist()


def test_onset_is_the_first_hour_above_twice_the_baseline():
    x = np.full(400, 100.0)
    x[300:310] = [150, 190, 260, 900, 4000, 3000, 900, 400, 250, 150]
    assert rad.onset_hour(x, start=250, stop=399) == 302


def test_cumulative_dose_converts_absorbed_dose_with_the_quality_factor():
    daily_ugy = np.full(10, 200.0)                            # 0.2 mGy/day
    cum = rad.cumulative_dose_msv(daily_ugy, quality_factor=3.0)
    assert cum[-1] == pytest.approx(10 * 0.2 * 3.0)


def test_cumulative_dose_fills_a_missing_day_with_the_recent_median():
    cum = rad.cumulative_dose_msv(np.array([200.0, 200.0, NAN, 200.0]), quality_factor=1.0)
    assert cum[-1] == pytest.approx(0.8)


def test_dose_status_is_yellow_at_80_percent_and_red_at_100():
    assert [rad.dose_status(v, budget_msv=100.0) for v in (50.0, 80.0, 99.9, 100.0)] == ["GREEN", "YELLOW", "YELLOW", "RED"]


def test_changepoint_score_sees_a_recent_step_up_and_nothing_on_a_flat_series():
    x = quiet(24 * 20)
    assert rad.changepoint_score(x, t=len(x) - 1) == 0.0
    x[-4:] *= 3
    assert rad.changepoint_score(x, t=len(x) - 1) > 10


def test_changepoint_score_ignores_a_step_that_is_no_longer_recent():
    x = quiet(24 * 20)
    x[-100:] *= 3
    assert rad.changepoint_score(x, t=len(x) - 1, recent=6) == 0.0


def test_bridge_merges_alerts_that_are_less_than_a_day_apart():
    a = np.zeros(100, bool)
    a[[10, 20, 70]] = True
    assert rad.count_events(a, gap_hours=24) == 2
