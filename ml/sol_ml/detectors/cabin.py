"""Cabin air: rolling CO2 averages and the rule-based environmental gate.

The limits are rules, not learned: NASA OCHMO-TB-004 (1-hour mean above 3 mmHg; 7-day mean above 2.5 mmHg).
When CO2 is high AND a crewmember reports headache or fatigue, the alert says "likely environmental"
and the first suggestion is ventilation rather than a medical work-up.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

LIMIT_1H_MMHG = 3.0
LIMIT_7D_MMHG = 2.5
WEEK_HOURS = 168


def rolling_mean(hourly: np.ndarray, hours: int = WEEK_HOURS, min_share: float = 0.5) -> np.ndarray:
    """Trailing mean over the last `hours` hourly values (this hour included); NaN until `min_share` of them exist."""
    return pd.Series(np.asarray(hourly, float)).rolling(hours, min_periods=int(np.ceil(hours * min_share))).mean().to_numpy()


def co2_high(one_hour: np.ndarray, seven_day: np.ndarray) -> np.ndarray:
    """True when the 1-hour mean is above 3 mmHg or the 7-day mean is above 2.5 mmHg."""
    one_hour, seven_day = np.asarray(one_hour, float), np.asarray(seven_day, float)
    return (np.nan_to_num(one_hour, nan=0.0) > LIMIT_1H_MMHG) | (np.nan_to_num(seven_day, nan=0.0) > LIMIT_7D_MMHG)


def likely_environmental(one_hour: np.ndarray, seven_day: np.ndarray, symptoms: np.ndarray) -> np.ndarray:
    """The gate: a headache or fatigue report while CO2 is high is attributed to the cabin first."""
    return co2_high(one_hour, seven_day) & np.asarray(symptoms, bool)


def reason(one_hour: float, seven_day: float) -> str:
    """One sentence naming the rule that fired, the value and the limit."""
    if one_hour > LIMIT_1H_MMHG:
        return (f"Cabin CO2 1-hour average is {one_hour:.2f} mmHg, above the {LIMIT_1H_MMHG:g} mmHg limit: "
                f"likely environmental, increase ventilation first.")
    return (f"Cabin CO2 7-day average is {seven_day:.2f} mmHg, above the {LIMIT_7D_MMHG:g} mmHg limit: "
            f"likely environmental, increase ventilation first.")
