"""Action protocols for a solo astronaut: what you do, and what goes to your flight surgeon on Earth.

Each condition maps to ordered actions per alert level. `who` is "self" (you) or "ground" (your flight surgeon,
reached with the communication delay of the mission). There is no crewmate or crew medical officer to hand work to,
so anything that needs a second person is either something you do yourself or something the flight surgeon decides.
The text mirrors docs/CLINICAL_PROTOCOLS.md.
"""
from __future__ import annotations

from .config import (DAILY_FLUID_TARGET_ML, SLEEP_TARGET_H, ARED_TARGET_MIN_WEEK,
                     AEROBIC_TARGET_MIN_WEEK)

S, G = "self", "ground"

PROTOCOLS: dict[str, dict[str, list[dict]]] = {
    "sleep_deprivation": {
        "YELLOW": [
            dict(who=S, action="Postpone safety-critical tasks (EVA, robotics, rover driving) until after your next full sleep."),
            dict(who=S, action="Take a 20-30 min nap in the sleep station if the schedule allows."),
            dict(who=S, action="Protect the next sleep window: lights dimmed 1 h before, no screens, eye mask and earplugs."),
            dict(who=S, action="Repeat the reaction-time test after the next sleep period."),
        ],
        "RED": [
            dict(who=S, action="Stop safety-critical work now; you are not cleared for EVA or robotics."),
            dict(who=G, action="Your sleep log and reaction-time trend have been sent to your flight surgeon for review."),
        ],
    },
    "dehydration": {
        "YELLOW": [
            dict(who=S, action="Drink 500 ml of water now, then about 250 ml every hour until urine colour is normal."),
            dict(who=S, action="Add an electrolyte drink pouch to the next 1 L of fluid."),
            dict(who=S, action="Postpone today's exercise session until heart rate returns to your baseline."),
            dict(who=S, action="Recheck vitals in 2 hours."),
        ],
        "RED": [
            dict(who=S, action="Stop activity and rest; drink oral rehydration solution now."),
            dict(who=S, action="Check for dizziness when standing; follow the dehydration checklist in the medical kit."),
            dict(who=G, action="Your flight surgeon has been notified and will advise on IV fluids from the kit."),
        ],
    },
    "co2_exposure": {
        "YELLOW": [
            dict(who=S, action="Increase ventilation first: check the cabin fan and CO2 scrubber for this module."),
            dict(who=S, action="Move to a well-ventilated module; avoid sleeping in a station with poor airflow."),
            dict(who=S, action="Log any headache, blurred vision or trouble concentrating in your check-in."),
        ],
        "RED": [
            dict(who=S, action="Leave the affected module now and close it until CO2 is below 3 mmHg."),
            dict(who=S, action="Run the CO2 scrubber off-nominal procedure and sweep with the portable CO2 monitor."),
            dict(who=G, action="Your flight surgeon and the life-support controllers have been notified."),
        ],
    },
    "cardiovascular_strain": {
        "YELLOW": [
            dict(who=S, action="Stop exercise and rest seated (strapped) for 15 minutes."),
            dict(who=S, action="Repeat blood pressure and heart rate measurement after rest."),
            dict(who=S, action="Avoid stimulants (caffeine) for the rest of the day."),
        ],
        "RED": [
            dict(who=S, action="Stop all activity now and rest."),
            dict(who=S, action="Record a 12-lead ECG with the medical kit and follow the chest-pain checklist."),
            dict(who=G, action="Your ECG and vitals have been sent to your flight surgeon."),
        ],
    },
    "fever_infection": {
        "YELLOW": [
            dict(who=S, action="Rest, increase fluids, and recheck temperature every 2 hours."),
            dict(who=S, action="Log your symptoms and check the medical kit for an antipyretic per the checklist."),
            dict(who=S, action="Clean the surfaces and equipment you have used."),
        ],
        "RED": [
            dict(who=S, action="Start the fever / infection checklist in the medical kit now."),
            dict(who=G, action="Your temperature trend and symptoms have been sent to your flight surgeon."),
        ],
    },
    "hypoxia": {
        "YELLOW": [
            dict(who=S, action="Re-seat the pulse oximeter and repeat the reading."),
            dict(who=S, action="Check the cabin oxygen and total pressure readings."),
            dict(who=S, action="Rest and slow your breathing; log shortness of breath or dizziness."),
        ],
        "RED": [
            dict(who=S, action="Put on an oxygen mask now."),
            dict(who=S, action="Check for a cabin leak or oxygen-system fault; follow the emergency checklist."),
            dict(who=G, action="Your flight surgeon and the life-support controllers have been notified."),
        ],
    },
    "radiation_event": {
        "YELLOW": [
            dict(who=S, action="Radiation is elevated: stop EVA preparation and check that the storm shelter is clear and stocked."),
            dict(who=S, action="Keep your dosimeter on and stay away from thinly shielded areas until the rate is back to normal."),
        ],
        "RED": [
            dict(who=S, action="Solar storm in progress: go to the storm shelter now."),
            dict(who=S, action="Abort any EVA or rover traverse and return to the habitat."),
            dict(who=S, action="Log your dosimeter reading when you enter and when you leave the shelter."),
            dict(who=G, action="Your flight surgeon has been notified; stay sheltered until the dose rate is below the elevated level."),
        ],
    },
    "physiological_drift": {
        "YELLOW": [
            dict(who=S, action="Take a full set of vitals now (temperature, blood pressure, SpO2) and log any symptoms."),
            dict(who=S, action="Protect tonight's sleep and keep fluids up; skip the hardest exercise set today."),
            dict(who=S, action="Recheck tomorrow morning."),
            dict(who=G, action="The trend goes to your flight surgeon in today's report: a slow rise in resting heart rate with poor sleep can come before an illness."),
        ],
        "RED": [dict(who=G, action="Your trend data has been sent to your flight surgeon.")],
    },
    "acute_deviation": {
        "YELLOW": [
            dict(who=S, action="Repeat the measurement to rule out a sensor or logging error."),
            dict(who=S, action="Note anything unusual in the last 24 h (workload, sleep, meals, medication)."),
            dict(who=G, action="If it is still far from your normal tomorrow, it goes to your flight surgeon in the daily report."),
        ],
        "RED": [dict(who=G, action="Your readings have been sent to your flight surgeon.")],
    },
    "unusual_combination": {
        "YELLOW": [
            dict(who=S, action="Check in with yourself: mood, stress and sleep have shifted together, each only a little."),
            dict(who=S, action="Use tonight's wind-down routine and schedule a family or friend call at the next comm pass."),
            dict(who=S, action="Keep a fixed day: meals, exercise and work blocks at the same times."),
            dict(who=G, action="Your flight surgeon sees this in today's report and can offer a private conference."),
        ],
        "RED": [dict(who=G, action="A private medical conference with your flight surgeon has been requested.")],
    },
    "low_mood": {
        "YELLOW": [
            dict(who=S, action="Several low days in a row are worth a conversation: book a private conference at the next comm pass."),
            dict(who=S, action="Keep exercise, daylight-spectrum lighting and regular meals: all three support mood."),
            dict(who=G, action="Your flight surgeon and the behavioural-health team receive this in today's report."),
        ],
        "RED": [dict(who=G, action="A private medical conference with your flight surgeon has been requested for today.")],
    },
    "deconditioning": {
        "YELLOW": [
            dict(who=S, action="The same exercise is costing more heartbeats: do not skip resistive (ARED) and aerobic sessions this week."),
            dict(who=S, action="Check sleep, hydration and nutrition, which also raise exercise heart rate."),
            dict(who=G, action="Your exercise log goes to your flight surgeon and the exercise specialist in today's report."),
        ],
        "RED": [dict(who=G, action="Your exercise log has been sent to your flight surgeon.")],
    },
    "low_blood_sugar": {
        "YELLOW": [
            dict(who=S, action="Eat or drink 15 g of fast sugar (juice pouch or glucose tablets) and recheck in 15 minutes."),
            dict(who=S, action="Do not start exercise or safety-critical work until glucose is back above 70 mg/dL."),
        ],
        "RED": [
            dict(who=S, action="Take fast sugar now and stay at rest; recheck every 15 minutes."),
            dict(who=S, action="Follow the hypoglycaemia checklist in the medical kit."),
            dict(who=G, action="Your flight surgeon has been notified."),
        ],
    },
    "high_blood_sugar": {
        "YELLOW": [
            dict(who=S, action="Repeat the fasting measurement tomorrow morning before eating."),
            dict(who=S, action="Drink water and log today's meals."),
            dict(who=G, action="If two fasting readings in a row are high, your flight surgeon reviews them."),
        ],
        "RED": [
            dict(who=S, action="Check for thirst, frequent urination or nausea and follow the hyperglycaemia checklist."),
            dict(who=G, action="Your flight surgeon has been notified."),
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
