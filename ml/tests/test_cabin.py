import numpy as np
import pandas as pd
import pytest

from sol_ml.data import osdr_eda
from sol_ml.detectors import cabin
from sol_ml.sim import co2 as co2_sim

NAN = np.nan


# ---------------------------------------------------------------- loader
def test_ppm_to_mmhg_at_one_atmosphere():
    assert osdr_eda.ppm_to_mmhg(3947.4) == pytest.approx(3.0, abs=0.001)
    assert osdr_eda.ppm_to_mmhg(5000) == pytest.approx(3.8)          # 0.5 % = 3.8 mmHg, the check value in DATASETS.md


def test_telemetry_loader_adds_mission_and_mmhg_and_drops_duplicate_times(tmp_path):
    (tmp_path / "RR-1_telemetry.csv").write_text(
        "time,temperature_iss,temperature_ground,humidity_iss,humidity_ground,co2_iss,co2_ground,milestones\n"
        "2014-09-20T03:59:00Z,24.1,24.1,39.0,37.0,2641.0,484.0,\n"
        "2014-09-20T03:59:00Z,24.1,24.1,,,,,\n"
        "2014-09-20T04:04:00Z,24.0,24.1,39.0,42.0,3947.4,480.0,Launch\n")
    df = osdr_eda.load_telemetry(tmp_path)
    assert df["mission"].unique().tolist() == ["RR-1"]
    assert len(df) == 2                                               # the two rows of 03:59 are merged
    assert df["co2_mmhg"].iloc[0] == pytest.approx(2641 * 760 / 1e6)
    assert df["co2_mmhg"].iloc[1] == pytest.approx(3.0, abs=0.001)
    assert str(df["time"].dt.tz) == "None"


def test_hourly_cabin_table_is_regular_with_missing_hours_kept(tmp_path):
    df = pd.DataFrame({"mission": "RR-1", "time": pd.to_datetime(["2020-01-01 00:05", "2020-01-01 00:35", "2020-01-01 02:10"]),
                       "co2_mmhg": [2.0, 3.0, 4.0], "temperature_iss": [22.0, 23.0, 24.0], "humidity_iss": [40.0, 40.0, 40.0]})
    h = osdr_eda.to_hourly(df)
    assert h["co2_mmhg"].tolist()[0] == 2.5 and np.isnan(h["co2_mmhg"].iloc[1]) and h["co2_mmhg"].iloc[2] == 4.0


# ---------------------------------------------------------------- gate
def test_seven_day_mean_is_trailing_and_needs_half_the_window():
    co2 = np.full(200, 2.0)
    co2[100:] = 3.0
    mean7 = cabin.rolling_mean(co2, hours=168)
    assert np.isnan(mean7[82]) and mean7[83] == 2.0
    assert mean7[199] == pytest.approx((68 * 2.0 + 100 * 3.0) / 168)


def test_co2_is_high_on_either_rule():
    one_hour = np.array([2.0, 3.1, 2.0, 2.0])
    seven_day = np.array([2.0, 2.0, 2.6, NAN])
    assert cabin.co2_high(one_hour, seven_day).tolist() == [False, True, True, False]


def test_gate_says_likely_environmental_only_with_symptoms_and_high_co2():
    one_hour = np.array([2.0, 3.5, 3.5, 2.0])
    seven_day = np.array([2.0, 2.0, 2.0, 2.0])
    symptoms = np.array([True, False, True, True])
    assert cabin.likely_environmental(one_hour, seven_day, symptoms).tolist() == [False, False, True, False]


def test_reason_names_the_rule_the_value_and_the_limit():
    text = cabin.reason(one_hour=3.4, seven_day=2.1)
    assert "3.4" in text and "3" in text and "1-hour" in text
    text = cabin.reason(one_hour=2.6, seven_day=2.7)
    assert "7-day" in text and "2.7" in text


# ---------------------------------------------------------------- CO2 generators
REAL = 2.4 + 0.3 * np.sin(np.arange(24 * 30) * 2 * np.pi / 24) + np.random.default_rng(0).normal(0, 0.15, 24 * 30)


@pytest.mark.parametrize("name", ["gaussian_diurnal", "ar1", "block_bootstrap"])
def test_generators_are_reproducible_positive_and_the_right_length(name):
    gen = co2_sim.GENERATORS[name]
    a = gen(REAL, n=500, rng=np.random.default_rng(42))
    b = gen(REAL, n=500, rng=np.random.default_rng(42))
    assert len(a) == 500 and np.all(a > 0) and np.array_equal(a, b)
    assert a.mean() == pytest.approx(REAL.mean(), abs=0.15)


def test_block_bootstrap_only_reuses_real_values():
    out = co2_sim.block_bootstrap(REAL, n=300, rng=np.random.default_rng(1), block=48)
    assert np.isin(out, REAL).all()


def test_ar1_keeps_the_hour_to_hour_memory_of_the_real_series():
    smooth = pd.Series(np.random.default_rng(3).normal(0, 1, 5000)).ewm(alpha=0.2).mean().to_numpy() + 5
    out = co2_sim.ar1(smooth, n=5000, rng=np.random.default_rng(2))
    real_r = np.corrcoef(smooth[:-1], smooth[1:])[0, 1]
    assert np.corrcoef(out[:-1], out[1:])[0, 1] == pytest.approx(real_r, abs=0.05)


def test_similarity_scores_are_zero_for_identical_series_and_worse_for_noise():
    same = co2_sim.similarity(REAL, REAL)
    assert same["ks"] == 0 and same["acf_rmse"] == pytest.approx(0) and same["diurnal_rmse"] == pytest.approx(0)
    noise = co2_sim.similarity(REAL, np.random.default_rng(5).normal(2.4, 0.5, len(REAL)))
    assert noise["ks"] > 0.1 and noise["acf_rmse"] > 0.1
