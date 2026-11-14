"""Daily brief: a short, personal read of your day and what to do about it.

Today it is written from your data by fixed templates. The response has the shape an AI model (Claude) will fill later,
so the app does not change when the model is connected. The brief explains and advises; it never changes your status,
the limits, or what is sent to your flight surgeon: the engine decides those.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

GENERATED_BY = {"kind": "rules", "label": "Written from your data by fixed rules",
                "note": "An AI version will write this card from the same data. It will explain and advise only; your status and alerts stay with the engine."}
WATCH = [  # (column, label, unit, worse when, size of a notable change)
    ("resting_hr", "Resting heart rate", "bpm", "up", 3.0),
    ("sleep_minutes", "Sleep", "h", "down", 45.0),
    ("mood", "Mood", "", "down", 1.0),
    ("stress", "Stress score", "", "down", 1.0),
    ("fatigue", "Energy", "", "down", 1.0),
    ("blood_glucose_mg_dl", "Fasting sugar", "mg/dL", "both", 12.0),
    ("urine_sg", "Urine concentration", "", "up", 0.006),
]
TIPS = {
    "radiation_event": "Stay in the storm shelter until the dose rate is back below the elevated level; the app tells you when.",
    "co2_exposure": "Ventilate first: check the fan and scrubber, and sleep in the best-ventilated module tonight.",
    "physiological_drift": "Treat today as a recovery day: easy exercise, extra fluids, early night.",
    "acute_deviation": "Repeat that measurement later today to rule out a sensor or logging error.",
    "unusual_combination": "Keep a fixed rhythm today and book a call home at the next comm pass.",
    "low_mood": "A short conversation helps: your flight surgeon can set up a private call.",
    "optic_disc_change": "Check your near vision with the chart and avoid heavy straining until your flight surgeon replies.",
    "dehydration": "Aim for 2.5-3 litres today and recheck the urine strip tomorrow morning.",
    "kidney_stone_risk": "Drink steadily through the day and log any pain in your side or back.",
    "constipation": "Add fibre and water today, and keep your exercise.",
    "diarrhea": "Oral rehydration solution with every loose stool.",
    "deconditioning": "Do not skip this week's resistive and aerobic sessions.",
}


def _fmt(col, v):
    if col == "sleep_minutes":
        return f"{v / 60:.1f} h"
    if col == "urine_sg":
        return f"{v:.3f}"
    return f"{v:.0f}"


def build(name: str, assessment: dict, daily: pd.DataFrame, d: int, reports: list[dict], unanswered: int) -> dict:
    first = name.split()[0]
    ts = pd.Timestamp(assessment["timestamp"])
    hour = ts.hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    status = assessment["status"]
    alerts = assessment["alerts"]

    if status == "GREEN":
        headline = "A steady day: everything is within your own normal."
    elif status == "YELLOW":
        headline = f"One thing to watch today: {alerts[0]['message'].lower()}."
    else:
        headline = f"Act now: {alerts[0]['message'][0].lower() + alerts[0]['message'][1:]}."

    changes = []
    if d >= 1:
        past = daily.iloc[max(0, d - 7): d]
        today = daily.iloc[d]
        for col, label, unit, worse, size in WATCH:
            if col not in daily or pd.isna(today.get(col)) or past[col].dropna().empty:
                continue
            base = float(past[col].median())
            delta = float(today[col]) - base
            if abs(delta) < size:
                continue
            bad = (worse == "up" and delta > 0) or (worse == "down" and delta < 0) or worse == "both"
            direction = "higher" if delta > 0 else "lower"
            changes.append({"label": label, "direction": "worse" if bad else "better",
                            "text": f"{label} is {_fmt(col, float(today[col]))}{(' ' + unit) if unit and col != 'sleep_minutes' else ''}, "
                                    f"{direction} than your last week ({_fmt(col, base)})."})

    paragraphs = []
    if alerts:
        paragraphs.append(alerts[0]["reason"])
        if len(alerts) > 1:
            paragraphs.append("Also: " + " ".join(a["reason"] for a in alerts[1:3]))
    else:
        paragraphs.append("Your heart, sleep, mood and morning tests are all close to your own normal, and the cabin air is within limits.")
    esc = assessment.get("escalation", {})
    if esc.get("status") == "sent":
        paragraphs.append("Your flight surgeon has already been sent this; keep following the steps while you wait for the reply.")
    elif esc.get("status") == "daily_report":
        paragraphs.append("It goes to your flight surgeon in tonight's report; nothing else is needed from you for that.")
    sent_week = [r for r in reports if (ts - pd.Timestamp(r["started_at"])).days < 7]
    if sent_week and status == "GREEN":
        paragraphs.append(f"{len(sent_week)} report(s) went to your flight surgeon this week; today needs nothing new.")

    tips = []
    for a in alerts:
        tip = TIPS.get(a["condition"])
        if tip and tip not in tips:
            tips.append(tip)
    for item in assessment.get("daily_plan", []):
        if item["category"] != "routine" and len(tips) < 3:
            tips.append(item["action"])
    if not tips:
        tips.append("Keep the routine that is working: sleep window, fluids and both exercise sessions.")

    ask_next = []
    if unanswered:
        ask_next.append(f"{unanswered} of today's questions are still open: answering them sharpens tomorrow's read.")

    return {"date": str(ts.date()), "greeting": f"{greeting}, {first}.", "headline": headline, "paragraphs": paragraphs,
            "changes": changes[:4], "tips": tips[:3], "ask_next": ask_next, "status": status, "generated_by": GENERATED_BY}
