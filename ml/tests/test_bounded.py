import numpy as np

from sol_ml.detectors import bounded, univariate

NAN = np.nan


def test_without_guards_it_is_the_plain_cusum():
    z = np.array([1.5, 2.0, NAN, -3.0, 4.0])
    assert np.array_equal(bounded.bounded_cusum(z, k=0.5), univariate.cusum(z, k=0.5))


def test_one_wild_day_cannot_carry_the_alarm_alone():
    z = np.array([0.0, 9.0, 0.0, 0.0])
    assert bounded.bounded_cusum(z, k=1.0, z_clip=4.0).tolist() == [0.0, 3.0, 2.0, 1.0]     # stays below h = 4
    assert univariate.cusum(z, k=1.0)[1] == 8.0


def test_the_cap_lets_the_alarm_clear_soon_after_the_signal_is_normal_again():
    z = np.concatenate([np.full(30, 3.0), np.zeros(10)])
    capped = bounded.bounded_cusum(z, k=1.0, cap=8.0)
    plain = univariate.cusum(z, k=1.0)
    assert capped[29] == 8.0 and plain[29] == 60.0
    assert (capped > 4.0)[30:].sum() == 3 and (plain > 4.0)[30:].all()


def test_guards_do_not_delay_the_first_crossing_of_a_steady_drift():
    z = np.full(20, 2.0)
    first = lambda s: int(np.argmax(s > 4.0))
    assert first(bounded.bounded_cusum(z, k=1.0, cap=8.0, z_clip=4.0)) == first(univariate.cusum(z, k=1.0))
