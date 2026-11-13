import numpy as np
import pandas as pd
import pytest

from sol_ml.detectors import baseline, body, evaluation, multivariate, univariate

NAN = np.nan


# ---------------------------------------------------------------- baseline
def test_badness_flips_signals_where_higher_is_better():
    df = pd.DataFrame({"resting_hr": [60.0], "sleep_minutes": [400.0], "fatigue": [2.0], "mood": [4.0], "stress": [3.0]})
    bad = baseline.to_badness(df)
    assert bad.loc[0, "resting_hr"] == 60 and bad.loc[0, "sleep_minutes"] == -400 and bad.loc[0, "fatigue"] == -2


def test_robust_scale_is_mad_based_for_continuous_data():
    x = np.array([1.0, 2.0, 3.0, 4.0, 100.0])
    assert baseline.robust_scale(x) == pytest.approx(1.4826 * 1.0)


def test_scale_falls_back_when_mad_is_zero_and_never_goes_below_floor_for_ordinal():
    mostly_three = np.array([3.0] * 9 + [2.0])                 # MAD = 0, mean abs deviation = 0.1
    assert baseline.robust_scale(mostly_three) == pytest.approx(1.2533 * 0.1)
    assert baseline.robust_scale(mostly_three, ordinal=True) == 0.5
    spread = np.array([1.0, 2.0, 3.0, 4.0, 5.0] * 2)
    assert baseline.robust_scale(spread, ordinal=True) == pytest.approx(1.4826 * 1.0)


def test_rolling_z_uses_only_previous_days():
    x = np.array([10.0, 11, 9, 10, 12, 8, 10, 30])
    z = baseline.rolling_z(x, window=7, min_periods=5)
    assert np.all(np.isnan(z[:5]))
    assert z[7] == pytest.approx((30 - 10) / (1.4826 * 1.0))   # today's spike is not part of its own baseline


def test_rolling_z_skips_missing_days_in_the_baseline():
    x = np.array([10.0, NAN, 11, 9, NAN, 10, 12, 8, 10, 30])
    z = baseline.rolling_z(x, window=9, min_periods=5)
    assert z[9] == pytest.approx((30 - 10) / (1.4826 * 1.0))
    assert np.isnan(z[1])


# ---------------------------------------------------------------- univariate
def test_threshold_alert_is_one_sided_by_default():
    z = np.array([[0.0, 0.0], [3.5, 0.0], [0.0, -3.5]])
    assert univariate.threshold_alerts(z, 3.0).tolist() == [False, True, False]
    assert univariate.threshold_alerts(z, 3.0, sided="both").tolist() == [False, True, True]


def test_cusum_accumulates_small_shifts_and_holds_through_missing_days():
    z = np.array([1.5, 1.5, NAN, 1.5, 1.5, 1.5])
    s = univariate.cusum(z, k=0.5)
    assert s.tolist() == [1.0, 2.0, 2.0, 3.0, 4.0, 5.0]
    assert univariate.cusum(np.array([1.0, -3.0, 1.0]), k=0.5).tolist() == [0.5, 0.0, 0.5]


def test_ewma_smooths_and_holds_through_missing_days():
    e = univariate.ewma(np.array([2.0, NAN, 2.0]), lam=0.5)
    assert e.tolist() == [1.0, 1.0, 1.5]
    assert univariate.ewma_limit(lam=0.2, L=3.0) == pytest.approx(3.0 * np.sqrt(0.2 / 1.8))


# ---------------------------------------------------------------- multivariate
def test_isolation_forest_flags_an_odd_combination_but_not_a_typical_day():
    rng = np.random.default_rng(0)
    train = rng.normal(size=(300, 3))
    model = multivariate.IsoForest(contamination=0.01, seed=0).fit(train)
    flags = model.flags(np.array([[0.1, -0.2, 0.0], [4.0, 4.0, 4.0]]))
    assert flags.tolist() == [False, True]


def test_mahalanobis_catches_a_combination_that_breaks_the_usual_correlation():
    rng = np.random.default_rng(0)
    a = rng.normal(size=400)
    train = np.column_stack([a, a + 0.1 * rng.normal(size=400)])      # the two signals normally move together
    model = multivariate.Mahalanobis(quantile=0.999).fit(train)
    flags = model.flags(np.array([[1.5, 1.5], [1.5, -1.5]]))          # each value alone is ordinary
    assert flags.tolist() == [False, True]


def test_multivariate_alerts_only_when_the_combination_points_to_worse():
    rng = np.random.default_rng(0)
    model = multivariate.IsoForest(contamination=0.01, seed=0).fit(rng.normal(size=(300, 3)))
    z = np.array([[4.0, 4.0, 4.0], [-4.0, -4.0, -4.0]])
    assert multivariate.worse_only(model.flags(z), z).tolist() == [True, False]


def test_rolling_flags_fit_on_past_days_only_and_start_after_min_history():
    rng = np.random.default_rng(1)
    z = rng.normal(size=(80, 3))
    z[60] = [5, 5, 5]
    flags = multivariate.rolling_flags(z, lambda: multivariate.IsoForest(0.01, seed=0), min_history=30, refit_every=7)
    assert not flags[:30].any()
    assert flags[60]


def test_missing_values_count_as_normal_and_sparse_days_are_never_flagged():
    z = np.array([[4.0, NAN, 4.0, 4.0], [4.0, NAN, NAN, NAN]])
    filled, ok = multivariate.prepare(z, min_observed=3)
    assert filled[0].tolist() == [4.0, 0.0, 4.0, 4.0]
    assert ok.tolist() == [True, False]


# ---------------------------------------------------------------- evaluation
def test_episodes_merge_consecutive_alert_days():
    assert evaluation.count_episodes(np.array([0, 1, 1, 0, 1, 0, 0, 1, 1, 1], bool)) == 3
    assert evaluation.count_episodes(np.zeros(5, bool)) == 0


def test_eval_mask_drops_warmup_and_two_days_around_injuries():
    injury = np.zeros(30, bool)
    injury[20] = True
    mask = evaluation.eval_mask(injury, warmup=14, pad=2)
    assert not mask[:14].any()
    assert mask[14:18].all() and not mask[18:23].any() and mask[23:].all()


def test_false_alarm_rate_is_episodes_per_30_evaluated_days():
    alerts = np.zeros(74, bool)
    alerts[[5, 30, 31, 50]] = True                    # day 5 is in the warm-up: not counted
    mask = evaluation.eval_mask(np.zeros(74, bool), warmup=14)
    assert evaluation.false_alarm_rate([alerts], [mask]) == pytest.approx(2 / (60 / 30))


def test_drift_injection_ramps_to_two_scales_over_seven_days_then_holds():
    x = np.zeros((40, 5))
    out = evaluation.inject(x, "drift_hr", start=10, scales=np.array([2.0, 50, 0.5, 0.5, 0.5]),
                            rng=np.random.default_rng(0))
    hr = out[:, 0]
    assert hr[9] == 0 and hr[10] == pytest.approx(4.0 / 7) and hr[16] == pytest.approx(4.0)
    assert hr[23] == pytest.approx(4.0) and hr[24] == 0          # held to the end of the 14-day window
    assert np.all(out[:, 1:] == 0)


def test_step_sleep_injection_lasts_five_days_and_keeps_missing_days_missing():
    x = np.zeros((40, 5))
    x[12, 1] = NAN
    out = evaluation.inject(x, "step_sleep", start=10, scales=np.array([2.0, 50, 0.5, 0.5, 0.5]),
                            rng=np.random.default_rng(0))
    assert out[10, 1] == 100 and out[14, 1] == 100 and out[15, 1] == 0
    assert np.isnan(out[12, 1])


def test_injected_self_reports_stay_whole_numbers_inside_the_scale():
    x = np.full((40, 5), -3.0)                                   # badness of a "3" on a 1-5 scale
    out = evaluation.inject(x, "combo_odd", start=10, scales=np.array([2.0, 50, 0.6, 0.6, 0.6]),
                            rng=np.random.default_rng(0))
    reports = out[10:15, 3:]                                     # mood and stress; fatigue is not in this case
    assert np.all(reports == np.round(reports)) and reports.min() >= -5 and reports.max() <= -1
    assert reports.mean() == pytest.approx(-3 + 1.5 * 0.6, abs=0.35)   # expected shift is kept by random rounding


def test_delay_counts_only_alerts_the_clean_series_did_not_already_have():
    clean = np.zeros(40, bool)
    clean[10] = True                                             # a false alarm that was there anyway
    injected = clean.copy()
    injected[13] = True
    assert evaluation.delay(clean, injected, start=10) == 3
    assert np.isnan(evaluation.delay(clean, clean, start=10))
    late = clean.copy()
    late[25] = True
    assert np.isnan(evaluation.delay(clean, late, start=10))     # after the 14-day window = missed


def test_summarize_reports_median_p90_and_miss_rate():
    s = evaluation.summarize(np.array([1.0, 2.0, 3.0, NAN]))
    assert s["median_delay"] == 2 and s["miss_rate"] == 0.25
    assert s["median_delay_censored"] == 2.5                     # misses count as 14 days


# ---------------------------------------------------------------- body detectors (whole pipeline on one person)
def _person(n=120, seed=0):
    rng = np.random.default_rng(seed)
    X = np.column_stack([60 + rng.normal(0, 2, n), -(400 + rng.normal(0, 50, n)),
                         -rng.choice([2.0, 3.0, 3.0, 3.0, 4.0], n), -rng.choice([2.0, 3.0, 3.0, 3.0, 4.0], n),
                         -rng.choice([2.0, 3.0, 3.0, 3.0, 4.0], n)])
    injury = np.zeros(n, bool)
    return evaluation.Person("t01", pd.date_range("2020-01-01", periods=n), X, injury,
                             evaluation.eval_mask(injury), np.array([2.0, 50.0, 0.6, 0.6, 0.6]))


def test_threshold_detector_flags_a_resting_hr_spike_day():
    p = _person()
    X = p.X.copy()
    X[80, 0] += 15
    alerts = body.threshold_detector(window=14, thr=3.0)(p, X)
    assert alerts[80] and alerts.sum() <= 4


def test_cusum_detector_catches_a_slow_drift_that_the_threshold_misses():
    p = _person()
    X = p.X.copy()
    X[80:, 0] += 5.0                                              # about 2.5 SD, sustained
    spike = body.threshold_detector(window=28, thr=3.5)(p, X)
    drift = body.cusum_detector(window=28, k=0.5, h=5.0)(p, X)
    assert not spike[80:94].any()                                 # no single day is extreme enough
    assert drift[80:94].any()                                     # but the small excesses add up


def test_any_of_alerts_when_either_detector_does():
    p = _person()
    first = lambda person, X, start=None: np.arange(len(X)) == 3
    second = lambda person, X, start=None: np.arange(len(X)) == 7
    assert np.flatnonzero(body.any_of(first, second)(p, p.X)).tolist() == [3, 7]


def test_pooled_multivariate_detector_is_trained_on_the_other_people():
    people = [_person(seed=s) for s in range(4)]
    for i, q in enumerate(people):
        q.name = f"t{i:02d}"
    det = body.multivariate_detector(lambda: multivariate.Mahalanobis(0.999), window=14, mode="pooled", people=people)
    X = people[0].X.copy()
    X[90, :] += np.array([6.0, 150.0, 2.0, 2.0, 2.0])             # everything worse on one day
    alerts = det(people[0], X)
    assert alerts[90] and alerts.sum() <= 5
    assert not det(people[0], people[0].X)[90]
