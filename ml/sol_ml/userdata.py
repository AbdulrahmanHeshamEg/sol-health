"""The astronaut's own entries: answers to the daily questions and uploaded eye photos, saved on this device.

    store = UserStore(DATA_DIR / "user")
    store.save_answers("2026-11-13", "2026-11-13T09:00:00", {"mood": 2, "urine_sg": 1.025})
    daily, hourly = store.apply(daily, hourly)          # entries replace the simulated values of that day / hour

Files live in data/user/ (git-ignored): answers.json and eye_photos/*.png with eye_photos.json.
Entries are REAL in the sense that the user typed or photographed them; they are tagged "you entered" in the app.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

DAILY_FIELDS = {"mood", "stress", "fatigue", "headache", "blood_glucose_mg_dl", "urine_sg", "urine_ph", "urine_blood",
                "urine_protein", "urine_glucose", "urine_ketones", "urine_leukocytes", "urine_nitrite", "stool_bristol",
                "stool_count", "stool_blood", "flank_pain", "vision_change", "infection_symptoms", "wants_conference",
                "fluid_litres_yesterday"}
HOURLY_FIELDS = {"systolic_bp", "diastolic_bp", "heart_rate", "spo2", "core_temp"}


class UserStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.answers_path = self.root / "answers.json"
        self.photos_dir = self.root / "eye_photos"
        self.photos_path = self.root / "eye_photos.json"

    # ---------------------------------------------------------------- answers
    def answers(self) -> dict:
        return json.loads(self.answers_path.read_text()) if self.answers_path.exists() else {}

    def save_answers(self, date: str, at: str, values: dict) -> dict:
        data = self.answers()
        day = data.setdefault(date, {"values": {}, "answered_at": at})
        day["values"].update(values)
        day["answered_at"] = at
        self.root.mkdir(parents=True, exist_ok=True)
        self.answers_path.write_text(json.dumps(data, indent=2))
        return day

    # ---------------------------------------------------------------- eye photos
    def photos(self) -> list[dict]:
        return json.loads(self.photos_path.read_text()) if self.photos_path.exists() else []

    def save_photo(self, date: str, mission_day: int, png: bytes, original_name: str) -> dict:
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        name = f"user_{date.replace(':', '').replace(' ', 'T')}.png"
        (self.photos_dir / name).write_bytes(png)
        entry = {"date": date, "mission_day": mission_day, "image": name, "uploaded": True, "original_name": original_name}
        items = [p for p in self.photos() if p["date"] != date] + [entry]
        self.photos_path.write_text(json.dumps(sorted(items, key=lambda p: p["date"]), indent=2))
        return entry

    def clear(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)

    # ---------------------------------------------------------------- overlay on the simulated data
    def apply(self, daily: pd.DataFrame, hourly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, set]:
        """Copies of the tables with the user's answers in place. Returns the set of (date, field) the user entered."""
        daily, hourly = daily.copy(), hourly.copy()
        entered = set()
        dates = pd.to_datetime(daily["date"]).dt.strftime("%Y-%m-%d")
        for date, day in self.answers().items():
            rows = daily.index[dates == date]
            for field, value in day["values"].items():
                if value is None:
                    continue
                if field == "sleep_hours" and len(rows):
                    daily.loc[rows, "sleep_minutes"] = float(value) * 60
                    entered.add((date, "sleep_minutes"))
                elif field in DAILY_FIELDS and len(rows):
                    if field not in daily:
                        daily[field] = pd.NA
                    daily.loc[rows, field] = value
                    entered.add((date, field))
                elif field in HOURLY_FIELDS:
                    when = pd.Timestamp(day["answered_at"]).floor("h")
                    hit = hourly.index[hourly["timestamp"] == when]
                    if len(hit):
                        hourly.loc[hit, field] = float(value)
                        hourly.loc[hit, "activity_level"] = hourly.loc[hit, "activity_level"].clip(upper=0.15)   # measured at rest
                        hourly.loc[hit, "is_asleep"] = 0
                        entered.add((date, field))
        return daily, hourly, entered
