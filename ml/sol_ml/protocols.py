"""Action protocols: what the astronaut (and crew medical officer) should do.

Each condition maps to ordered actions per alert level. Actions are written for a
decision-support display: short, imperative, and always ending in escalation to the
Crew Medical Officer (CMO) / flight surgeon when severity is RED.
The text mirrors docs/CLINICAL_PROTOCOLS.md.
"""
from __future__ import annotations

from .config import (DAILY_FLUID_TARGET_ML, SLEEP_TARGET_H, ARED_TARGET_MIN_WEEK,
                     AEROBIC_TARGET_MIN_WEEK)

# who: "self" (the astronaut), "cmo" (crew medical officer), "ground" (flight surgeon), "crew"
PROTOCOLS: dict[str, dict[str, list[dict]]] = {
    "sleep_deprivation": {
        "YELLOW": [
            dict(who="self", action="Move safety-critical tasks (EVA prep, robotics, docking) to a rested crewmate today."),
            dict(who="self", action="Take a 20-30 min nap in the sleep station if the schedule allows."),
            dict(who="self", action="Protect the next sleep window: lights dimmed 1 h before, no screens, eye mask and earplugs."),
            dict(who="self", action="Repeat the reaction-time (PVT) test after the next sleep period."),
        ],
        "RED": [
            dict(who="self", action="Stop safety-critical work now; you are not cleared for EVA or robotics."),
            dict(who="cmo", action="CMO to review sleep log and medications; consider schedule shift."),
            dict(who="ground", action="Notify flight surgeon at next comm pass with sleep and PVT trend."),
        ],
    },
    "dehydration": {
        "YELLOW": [
            dict(who="self", action="Drink 500 ml of water now, then about 250 ml every hour until urine color normalizes."),
            dict(who="self", action="Add an electrolyte drink pouch to the next 1 L of fluid."),
            dict(who="self", action="Postpone today's exercise session until heart rate returns to your baseline."),
            dict(who="self", action="Recheck vitals in 2 hours."),
        ],
        "RED": [
            dict(who="self", action="Stop activity and rest; drink oral rehydration solution now."),
            dict(who="cmo", action="CMO to check orthostatic symptoms and consider IV fluids per the medical checklist."),
            dict(who="ground", action="Contact flight surgeon now."),
        ],
    },
    "co2_exposure": {
        "YELLOW": [
            dict(who="self", action="Move to a well-ventilated module; avoid sleeping in a station with poor airflow."),
            dict(who="crew", action="Check the cabin fan and CO2 scrubber status for this module."),
            dict(who="self", action="Report headache, blurred vision or trouble concentrating to the CMO."),
        ],
        "RED": [
            dict(who="crew", action="Leave the affected module now and isolate it until ppCO2 is below 3 mmHg."),
            dict(who="crew", action="Run the CO2 scrubber off-nominal procedure; consider a portable CO2 monitor sweep."),
            dict(who="ground", action="Notify flight surgeon and ECLSS flight controller."),
        ],
    },
    "cardiovascular_strain": {
        "YELLOW": [
            dict(who="self", action="Stop exercise and rest seated (strapped) for 15 minutes."),
            dict(who="self", action="Repeat blood pressure and heart rate measurement after rest."),
            dict(who="self", action="Avoid stimulants (caffeine) for the rest of the day."),
        ],
        "RED": [
            dict(who="self", action="Stop all activity now and tell the CMO."),
            dict(who="cmo", action="CMO to record a 12-lead ECG and follow the chest-pain / arrhythmia checklist."),
            dict(who="ground", action="Contact flight surgeon now with ECG data."),
        ],
    },
    "fever_infection": {
        "YELLOW": [
            dict(who="self", action="Rest, increase fluids, and recheck temperature every 2 hours."),
            dict(who="self", action="Wear a mask and limit close contact with crewmates; clean shared surfaces."),
            dict(who="cmo", action="CMO to log symptoms and check the medical kit for antipyretics per checklist."),
        ],
        "RED": [
            dict(who="cmo", action="CMO to examine now and start the fever / infection checklist."),
            dict(who="crew", action="Isolate the crewmember in a separate sleep station."),
            dict(who="ground", action="Contact flight surgeon now."),
        ],
    },
    "hypoxia": {
        "YELLOW": [
            dict(who="self", action="Re-seat the pulse oximeter and repeat the reading."),
            dict(who="crew", action="Check cabin oxygen partial pressure and total pressure readings."),
            dict(who="self", action="Rest and slow breathing; report shortness of breath or dizziness."),
        ],
        "RED": [
            dict(who="self", action="Put on an oxygen mask now."),
            dict(who="crew", action="Check for cabin leak or O2 system fault; follow the emergency checklist."),
            dict(who="ground", action="Contact flight surgeon and ECLSS now."),
        ],
    },
}


def actions_for(condition: str, level: str) -> list[dict]:
    if condition == "nominal" or level == "GREEN":
        return []
    acts = list(PROTOCOLS.get(condition, {}).get("YELLOW", []))
    if level == "RED":
        acts = PROTOCOLS[condition]["RED"] + acts
    return [dict(a, condition=condition, level=level, priority=i + 1) for i, a in enumerate(acts)]


def daily_plan(summary: dict) -> list[dict]:
    """Routine guidance from the last 24 h / 7 days, shown even when everything is GREEN.

    summary keys: sleep_last_24h, fluid_last_24h, ared_minutes_7d, aerobic_minutes_7d
    """
    plan = []
    if summary["sleep_last_24h"] < SLEEP_TARGET_H - 1:
        plan.append(dict(who="self", category="sleep",
                         action=f"Aim for {SLEEP_TARGET_H:.0f} h sleep tonight (last 24 h: {summary['sleep_last_24h']:.0f} h)."))
    if summary["fluid_last_24h"] < DAILY_FLUID_TARGET_ML * 0.8:
        plan.append(dict(who="self", category="hydration",
                         action=f"Drink to reach {DAILY_FLUID_TARGET_ML} ml today (last 24 h: {summary['fluid_last_24h']:.0f} ml)."))
    if summary["ared_minutes_7d"] < ARED_TARGET_MIN_WEEK * 0.85:
        gap = ARED_TARGET_MIN_WEEK - summary["ared_minutes_7d"]
        plan.append(dict(who="self", category="exercise",
                         action=f"Add {gap:.0f} min of resistive (ARED) exercise this week to protect bone and muscle."))
    if summary["aerobic_minutes_7d"] < AEROBIC_TARGET_MIN_WEEK * 0.85:
        gap = AEROBIC_TARGET_MIN_WEEK - summary["aerobic_minutes_7d"]
        plan.append(dict(who="self", category="exercise",
                         action=f"Add {gap:.0f} min of aerobic exercise (treadmill/cycle) this week."))
    if not plan:
        plan.append(dict(who="self", category="routine",
                         action="All routine targets met. Keep the current sleep, hydration and exercise schedule."))
    return plan
