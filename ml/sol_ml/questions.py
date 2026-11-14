"""Today's questions: what the engine asks the astronaut, and why. The frontend only renders them.

Routine questions come every day (how you feel, morning tests, stool log); follow-up questions appear when the
engine sees something it needs to know more about (CO2 is high: do you have a headache? blood in the urine: any pain
in your side?). Each question names the field its answer fills, so answers go straight back into the engine.
"""
from __future__ import annotations

import pandas as pd

SCALE = {
    "mood": ["Very low", "Low", "Okay", "Good", "Very good"],
    "stress": ["Very stressed", "Stressed", "Normal", "Calm", "Very relaxed"],
    "fatigue": ["Exhausted", "Tired", "Normal", "Fresh", "Very fresh"],
}
DIPSTICK = [{"value": 0, "label": "Negative"}, {"value": 1, "label": "Trace"}, {"value": 2, "label": "+"}, {"value": 3, "label": "++"}]
BRISTOL = [{"value": 1, "label": "Type 1: separate hard lumps"}, {"value": 2, "label": "Type 2: lumpy, sausage-shaped"},
           {"value": 3, "label": "Type 3: sausage with cracks"}, {"value": 4, "label": "Type 4: smooth and soft"},
           {"value": 5, "label": "Type 5: soft blobs"}, {"value": 6, "label": "Type 6: mushy"}, {"value": 7, "label": "Type 7: watery"}]
YESNO = [{"value": 1, "label": "Yes"}, {"value": 0, "label": "No"}]


def _scale(field, text, why):
    return {"field": field, "text": text, "why": why, "type": "choice",
            "options": [{"value": i + 1, "label": f"{i + 1} · {w}"} for i, w in enumerate(SCALE[field])]}


def _number(field, text, why, unit, lo, hi, step):
    return {"field": field, "text": text, "why": why, "type": "number", "unit": unit, "min": lo, "max": hi, "step": step}


def _yesno(field, text, why):
    return {"field": field, "text": text, "why": why, "type": "choice", "options": YESNO}


ROUTINE = [
    {"id": "feel", "title": "How you feel", "questions": [
        _number("sleep_hours", "How many hours did you sleep last night?", "Sleep protects attention and mood; your watch can miss short wake-ups.", "hours", 0, 16, 0.25),
        _scale("mood", "How is your mood today?", "A daily score makes a slow change visible long before it feels serious."),
        _scale("stress", "How stressed do you feel?", "Stress, mood and sleep moving together is an early sign worth acting on."),
        _scale("fatigue", "How is your energy?", "Fatigue with a rising resting heart rate can come before an illness."),
        _yesno("headache", "Do you have a headache?", "A headache while cabin CO2 is high is probably the air, not you."),
    ]},
    {"id": "morning_tests", "title": "Morning tests", "questions": [
        _number("blood_glucose_mg_dl", "Fasting blood sugar, before breakfast", "Low or high sugar affects thinking and energy.", "mg/dL", 20, 600, 1),
        _number("urine_sg", "Urine dipstick: specific gravity", "Shows how concentrated your urine is: high means drink more.", "", 1.000, 1.040, 0.005),
        {"field": "urine_blood", "text": "Urine dipstick: blood pad", "why": "Blood can be the first sign of a kidney stone; bone loss in space raises that risk.", "type": "choice", "options": DIPSTICK},
        {"field": "urine_leukocytes", "text": "Urine dipstick: white-cell pad", "why": "White cells with nitrite point to a urinary infection.", "type": "choice", "options": DIPSTICK},
        _yesno("urine_nitrite", "Urine dipstick: is the nitrite pad positive?", "Nitrite comes from bacteria in the urine."),
        {"field": "urine_protein", "text": "Urine dipstick: protein pad", "why": "Protein in urine is normally absent; if it stays, the kidneys need a look.", "type": "choice", "options": DIPSTICK},
    ]},
    {"id": "stool", "title": "Stool log", "questions": [
        {"field": "stool_bristol", "text": "What did your stool look like today? (Bristol chart)", "why": "Types 3-5 are normal; hard or watery stools change your fluid needs.", "type": "choice", "options": BRISTOL},
        _number("stool_count", "How many times today?", "Three or more loose stools a day dehydrates fast.", "times", 0, 10, 1),
        _yesno("stool_blood", "Any blood in your stool?", "Your flight surgeon should hear about any blood."),
    ]},
    {"id": "vitals", "title": "Vitals check (seated, at rest)", "optional": True, "questions": [
        _number("systolic_bp", "Blood pressure: upper number", "Blood pressure is judged at rest; your cuff reading replaces this hour's sensor value.", "mmHg", 50, 260, 1),
        _number("diastolic_bp", "Blood pressure: lower number", "The lower number completes the reading.", "mmHg", 30, 160, 1),
        _number("core_temp", "Body temperature", "Fever is the clearest sign of infection.", "°C", 33, 43, 0.1),
    ]},
]


def follow_ups(assessment: dict, daily_row: pd.Series | None, eye_due: bool) -> list[dict]:
    """Questions the engine adds because of what it sees right now."""
    qs = []
    kinds = {a["kind"] for a in assessment["alerts"]}
    conds = {a["condition"] for a in assessment["alerts"]}
    signals = {a.get("signal") for a in assessment["alerts"]}
    if assessment["context"].get("cabin_co2_high"):
        qs.append(dict(_yesno("headache", "Cabin CO2 is high. Do you have a headache right now?",
                              "If yes, the app treats it as likely environmental and asks you to ventilate first."), trigger="Cabin CO2 is high"))
    if kinds & {"drift", "spike"} and signals & {"resting_hr", "fatigue", "sleep_minutes"}:
        qs.append(dict(_yesno("infection_symptoms", "Your resting heart rate or sleep has moved from your normal. Any sore throat, cough or feverish feeling?",
                              "A slow drift can be the start of an illness; this tells your flight surgeon which."), trigger="Slow drift from your normal"))
    if "kidney_stone_risk" in conds:
        qs.append(dict(_yesno("flank_pain", "Your urine shows blood. Any pain in your side, back or groin?",
                              "Blood with that pain points to a kidney stone, and goes to your flight surgeon at once."), trigger="Blood in urine"))
    if "dehydration" in conds:
        qs.append(dict(_number("fluid_litres_yesterday", "How much did you drink yesterday?", "Helps your flight surgeon judge how dry you are.", "litres", 0, 8, 0.25),
                       trigger="Concentrated urine"))
    if "optic_disc_change" in conds:
        qs.append(dict(_yesno("vision_change", "Your eye photo changed. Is your near vision blurry or different?",
                              "A vision change with a swollen optic disc goes to your flight surgeon at once."), trigger="Eye photo changed"))
    if conds & {"low_mood", "unusual_combination"}:
        qs.append(dict(_yesno("wants_conference", "Would you like a private call with your flight surgeon at the next comm pass?",
                              "Several low days are worth a conversation; nobody else sees your answer."), trigger="Mood and stress have shifted"))
    if eye_due:
        qs.append({"field": "fundus_photo", "type": "photo", "text": "Your monthly eye photo is due. Take a fundus photo of your right eye and upload it.",
                   "why": "The app compares it with your baseline photo to catch optic disc swelling (SANS) early.", "trigger": "Monthly eye exam"})
    return qs


def build(assessment: dict, daily_row: pd.Series | None, answered: dict, eye_due: bool) -> dict:
    """Groups of questions for today, each marked answered (with the value) when the user has answered it."""
    groups = [{"id": "follow_up", "title": "The app needs to know", "questions": follow_ups(assessment, daily_row, eye_due)}] + \
             [{k: v for k, v in g.items()} | {"questions": [dict(q) for q in g["questions"]]} for g in ROUTINE]
    total = done = 0
    for g in groups:
        for q in g["questions"]:
            q["answered"] = q["field"] in answered
            q["answer"] = answered.get(q["field"])
            if not g.get("optional") and q["type"] != "photo":
                total += 1
                done += q["answered"]
    groups = [g for g in groups if g["questions"]]
    return {"groups": groups, "answered": done, "total": total}


def validation_ranges() -> dict:
    """field -> (min, max) for every question, used to reject impossible answers."""
    out = {}
    for g in ROUTINE:
        for q in g["questions"]:
            if q["type"] == "number":
                out[q["field"]] = (q["min"], q["max"])
            else:
                vals = [o["value"] for o in q["options"]]
                out[q["field"]] = (min(vals), max(vals))
    out.update({"infection_symptoms": (0, 1), "flank_pain": (0, 1), "vision_change": (0, 1), "wants_conference": (0, 1),
                "fluid_litres_yesterday": (0, 8), "urine_ph": (4, 9), "urine_glucose": (0, 3), "urine_ketones": (0, 3)})
    return out
