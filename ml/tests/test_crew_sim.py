import numpy as np
import pandas as pd
import pytest

from sol_ml.detectors import cabin as gate
from sol_ml.detectors import radiation as rad
from sol_ml.sim import crew

HAVE_DATA = all((crew.PROCESSED / f).exists() for f in
                ("pmdata_daily.parquet", "pmdata_hourly_hr.parquet", "iss_cabin.parquet", "msl_rad_hourly.parquet"))
needs_data = pytest.mark.skipif(not HAVE_DATA, reason="processed real data not built (run notebooks 01, 04, 06)")


def test_transition_matrix_counts_day_to_day_moves_and_ignores_gaps():
    m = crew.transition_matrix(np.array([3, 3, 3, 2, np.nan, 3, 3]), smoothing=0.0 + 1e-9)
    assert m[2, 2] == pytest.approx(3 / 4) and m[2, 1] == pytest.approx(1 / 4)
    assert np.allclose(m.sum(axis=1), 1)


def test_generated_resting_hr_keeps_the_fitted_memory_and_spread():
    p = {"mean": 60.0, "between_sd": 6.0, "within_sd": 2.0, "phi": 0.8}
    x = crew.gen_resting_hr(p, 20000, np.random.default_rng(0), mean=60.0)
    assert np.corrcoef(x[:-1], x[1:])[0, 1] == pytest.approx(0.8, abs=0.02)
    assert x.std() == pytest.approx(2.0, abs=0.1) and x.mean() == pytest.approx(60, abs=0.2)


def test_generated_report_stays_on_the_scale_and_follows_the_matrix():
    sticky = np.full((5, 5), 0.025)
    np.fill_diagonal(sticky, 0.9)
    r = crew.gen_report(sticky, 5000, np.random.default_rng(1))
    assert set(np.unique(r)) <= {1.0, 2.0, 3.0, 4.0, 5.0}
    assert (r[1:] == r[:-1]).mean() == pytest.approx(0.9, abs=0.02)


def test_sleep_minutes_resample_real_residuals_inside_limits():
    p = {"mean": 400.0, "between_sd": 30.0, "within_sd": 60.0, "residuals": np.array([-5.0, 0.0, 0.5, 5.0])}
    s = crew.gen_sleep_minutes(p, 200, np.random.default_rng(2), mean=400.0)
    assert s.min() == 180 and s.max() == 600 and set(np.unique(s)) <= {180.0, 400.0, 430.0, 600.0}


def test_asleep_mask_ends_each_night_at_six_with_the_right_length():
    mask = crew.asleep_mask(np.array([480.0, 300.0]))
    assert mask[:6].sum() == 6 and mask[6:24].sum() == 0          # first night is cut by the start of the series
    assert mask[24 + 1: 24 + 6].sum() == 5 and mask[24] == 0      # 5 hours: 01:00-06:00


def test_slow_drift_ramps_then_holds_and_leaves_earlier_days_alone():
    daily = pd.DataFrame({"mission_day": np.arange(1, 31), "resting_hr": 60.0, "sleep_minutes": 420.0, "fatigue": 3.0})
    out = crew.plant_slow_drift(daily, start_day=11, days=10, rng=np.random.default_rng(0))
    assert out.resting_hr.iloc[9] == 60 and out.resting_hr.iloc[10] == pytest.approx(60.6)
    assert out.resting_hr.iloc[19] == 66 and out.resting_hr.iloc[29] == 66
    assert out.sleep_minutes.iloc[19] == 360 and out.fatigue.iloc[25] == 2
    assert daily.resting_hr.max() == 60


def test_odd_combination_moves_three_signals_a_little_for_a_week():
    daily = pd.DataFrame({"mission_day": np.arange(1, 21), "sleep_minutes": 420.0, "mood": 3.0, "stress": 3.0, "fatigue": 3.0})
    out = crew.plant_odd_combination(daily, start_day=5, days=7)
    week = out[out.mission_day.between(5, 11)]
    assert (week.mood == 2).all() and (week.stress == 2).all() and (week.sleep_minutes == 365).all()
    assert (week.fatigue == 3).all() and out.mood.iloc[11] == 3


def test_splice_cross_fades_into_the_segment():
    out = crew.splice(np.zeros(100), np.full(40, 10.0), start=30, fade=10)
    assert out[29] == 0 and out[30] == pytest.approx(1.0) and out[45] == 10 and out[69] == pytest.approx(1.0) and out[70] == 0


def test_highest_stretch_finds_the_real_high_period():
    x = np.concatenate([np.full(50, 2.0), np.full(30, 4.0), np.full(50, 2.0)])
    assert np.all(crew.highest_stretch(x, 30) == 4.0)


def test_radiation_replay_puts_the_storm_onset_on_the_requested_hour():
    hours = pd.date_range("2024-05-01", "2024-06-10", freq="1h")
    dose = np.full(len(hours), 150.0)
    dose[hours.get_loc(crew.STORM_ONSET)] = 3000.0
    out = crew.radiation_replay(pd.DataFrame({"hour": hours, "dose_e": dose}), n_hours=400, storm_hour=300)
    assert len(out) == 400 and out.iloc[300] == 3000 and out.iloc[299] == 150


@needs_data
def test_demo_is_reproducible_and_has_the_expected_shape():
    a, b = crew.build_demo(seed=42), crew.build_demo(seed=42)
    assert a["telemetry"].equals(b["telemetry"]) and a["daily"].equals(b["daily"])
    assert len(a["crew"]) == 1 and len(a["telemetry"]) == 75 * 24 and len(a["daily"]) == 75          # one astronaut
    for col in ("heart_rate", "spo2", "systolic_bp", "core_temp", "cabin_co2_mmhg", "radiation_msv", "radiation_ugy_per_day", "is_asleep"):
        assert col in a["telemetry"].columns
    assert [c["id"] for c in a["planted_cases"]] == ["cabin_co2", "slow_drift", "solar_storm", "optic_disc", "odd_combination"]
    assert set(a["sources"][k]["kind"] for k in a["sources"]) == {"simulated", "real"}


@needs_data
def test_demo_contains_the_planted_cabin_and_storm_events():
    demo = crew.build_demo(seed=42)
    one = demo["telemetry"][demo["telemetry"].astronaut_id == "UH-01"]
    seven_day = gate.rolling_mean(one.cabin_co2_mmhg.to_numpy())
    assert np.nanmax(seven_day[23 * 24: 34 * 24]) > gate.LIMIT_7D_MMHG          # the planted cabin case
    assert np.nanmax(seven_day[: 20 * 24]) < gate.LIMIT_7D_MMHG                 # quiet before it
    ratio = rad.spe_score(one.radiation_ugy_per_day.to_numpy(), "ratio")
    storm = 74 * 24 + 5
    assert ratio[storm] > 2 and np.nanmax(ratio[200: storm - 24]) < 1.3
    daily = demo["daily"]
    assert daily[(daily.astronaut_id == "UH-01") & daily.mission_day.between(27, 33)].headache.all()
