# API Reference

Base URL: `http://localhost:8000`. Interactive docs: `/docs`. All responses are JSON.
Every `GET` under `/api/crew/{id}`, plus `/api/crew` and `/api/mission`, accepts `at=<ISO timestamp>` to replay the mission at that hour.

**The app is personal (14 Nov 2026):** the mission has one astronaut. `/api/me` names them; the per-person routes keep the `/api/crew/{id}` path so the v0 contract stays valid. Actions are either the astronaut's (`self`) or the flight surgeon's (`ground`).
Real example responses: `data/demo/api_snapshots/` (current moment) and `data/demo/api_snapshots/at/<mark>/` (replay marks).

**v2 keeps the v0 response shape and only adds fields and endpoints.** New items are marked *(new)*.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness `{ "ok": true }` |
| GET | `/api/mission` | Mission info, `now`, `time_range`, `replay_marks` *(new)* |
| GET | `/api/meta` | Condition ids/labels, signal names, levels, `hazards`, `sources`, `citations` *(new)* |
| GET | `/api/indicators` *(new)* | Explainer cards per indicator |
| GET | `/api/demo/cases` *(new)* | The planted test cases (ground truth, for replay buttons and evaluation) |
| GET | `/api/me` *(new)* | The astronaut this app belongs to, and their flight surgeon (title, where, one-way delay) |
| GET | `/api/crew` | Status cards (one in the solo mission), sorted worst-first |
| GET | `/api/crew/{id}` | Profile (age, role, baseline, exercise plan, prior dose) |
| GET | `/api/crew/{id}/vitals?hours=72` | Raw hourly telemetry rows |
| GET | `/api/crew/{id}/daily?days=30` *(new)* | Daily indicators with the body models' flags |
| GET | `/api/crew/{id}/assessment` | Full current assessment |
| GET | `/api/crew/{id}/timeline?hours=72` | Hour-by-hour status |
| GET | `/api/crew/{id}/forecast?horizon_days=90` | Bone / muscle projection, fitness trend |
| GET | `/api/crew/{id}/radiation` | Dose vs career limit, storm level |
| GET | `/api/crew/{id}/reminders` *(new)* | Measurements due now, check-in streak |
| GET | `/api/crew/{id}/reports` *(new)* | Everything sent to the flight surgeon so far, newest first |
| POST | `/api/assess` | Assess a custom series, or apply a manual check-in |

Errors: `404` unknown astronaut, `422` bad `at`, fewer than 24 h of history, or an out-of-range check-in value.

## `GET /api/mission`
`mission_id`, `name`, `vehicle`, `setting` (`mars_surface`), `start`, `planned_duration_days` (500), `current_day` (75),
`radiation_msv_per_day_assumed`, `earth_comm_delay_s`, `note`, `now`, `time_range{start,end}`,
`radiation_replay{dataset,from,to}`, `cabin_co2_source{base,planted_high}`,
`replay_marks[]: { id, label, at, astronaut_id }` (the start of each planted case).

## `GET /api/crew` → `CrewCard[]`
```ts
type Level = "GREEN" | "YELLOW" | "RED";
interface CrewCard {
  astronaut_id: string; name: string; role: string;
  status: Level; health_score: number;          // 0..100
  condition: string; condition_label: string;
  top_alert: string | null;
  top_reason: string | null;                    // (new) one-sentence reason of the top alert
  vitals: Record<VitalName, number>;            // latest values
  cabin_co2_mmhg: number;                       // (new)
  timestamp: string;
}
```

## `GET /api/crew/{id}/assessment` → `Assessment`
```ts
type VitalName = "heart_rate"|"hrv_rmssd"|"spo2"|"resp_rate"|"systolic_bp"|"diastolic_bp"|"core_temp"|"pvt_reaction_ms";
type Source = { kind: "real" | "simulated"; dataset?: string; calibrated_on?: string };
interface Alert {
  source: "rule" | "model"; level: Level; condition: string; message: string;
  reason: string;                               // (new) one sentence: signal, how far from normal, for how long
  kind: "hard_limit"|"spike"|"drift"|"combination"|"environmental_gate"|"spe"|"mood"|"fitness_trend";   // (new)
  hazard: string;                               // (new) NASA hazard behind it, e.g. "Radiation"
  signal?: string; value?: number; threshold?: string;
  probability?: number;                         // model alerts: strength 0..1 (not a calibrated probability)
  model?: string; z?: number; cusum?: number;   // (new) model alerts
}
interface Assessment {
  astronaut_id: string; timestamp: string; mission_day: number;
  status: Level; health_score: number;
  condition: string; condition_label: string;
  probabilities: Record<string, number>;        // relative evidence per condition, sums to 1 (14 conditions, see /api/meta)
  anomaly_score: number;                        // 0..1: share of real training days less unusual than today
  alerts: Alert[];                              // worst first
  drivers: Array<{ signal: string; deviation: number; unit: string; z: number }>;   // daily signals, positive z = worse
  vitals: Record<VitalName, { value: number; baseline: number; delta: number; unit: string; source: Source }>;
  indicators: Record<"resting_hr"|"sleep_hours"|"fatigue"|"mood"|"stress"|"blood_glucose_mg_dl",     // (new)
    { label: string; value: number; baseline: number|null; delta: number|null; unit: string; z: number|null; date: string; source: Source }>;
  body_systems: Array<{ id: "heart"|"lungs"|"brain"|"bones_muscles"|"blood"|"immune"; label: string;   // (new) for the body figure
    function: string; status: Level; summary: string; indicators: string[]; alerts: string[] }>;
  context: { activity_level: number; is_asleep: 0|1; cabin_co2_mmhg: number;
             sleep_last_24h: number; fluid_last_24h: number; ared_minutes_7d: number; aerobic_minutes_7d: number;
             cabin_co2_7d_mean_mmhg: number|null; cabin_co2_high: boolean;                             // (new)
             radiation_ratio_to_7d: number; radiation_level: Level };                                  // (new)
  actions: Array<{ who: "self"|"ground"; action: string; condition: string; level: Level; priority: number }>;   // ground = your flight surgeon
  daily_plan: Array<{ who: "self"; category: "sleep"|"hydration"|"exercise"|"routine"; action: string }>;
  escalation: {                                 // (new) what reaches the flight surgeon
    status: "sent" | "daily_report" | "none";   // RED: sent at once; YELLOW: in the daily report at 20:00
    to: string; level: Level; sent_at: string|null; arrives_at: string|null; summary: string; items: string[] };
  fitness_trend: { alert: boolean; shift_bpm: number; weeks_ago: number; sessions: number; reason: string };   // (new)
  disclaimer: string;
}
```
`actions` now cover every active alert (RED first), not only the primary condition.

## `GET /api/crew/{id}/vitals` → `TelemetryRow[]`
Fields: `timestamp, astronaut_id, mission_day, hour`, the 8 vitals, `activity_level, is_asleep, exercise_type
("none"|"resistive"|"aerobic"), fluid_intake_ml, cabin_co2_mmhg, radiation_msv`, and *(new)* `radiation_ugy_per_day`
(dose rate). See `DATA_DICTIONARY.md`.

## `GET /api/crew/{id}/daily` → `DailyRow[]` *(new)*
`astronaut_id, date, mission_day, resting_hr, sleep_minutes, sleep_hours, fatigue, mood, stress (1–5, 5 = best), headache (0/1),
blood_glucose_mg_dl, flag_spike, flag_drift, flag_combo`.

## `GET /api/crew/{id}/timeline` → `TimelinePoint[]`
`{ timestamp, status, condition, p_abnormal (0..1), anomaly_score (0..1) }`: use `p_abnormal > 0.5` for chart shading (`status` is new).

## `GET /api/crew/{id}/forecast`
```ts
interface Forecast {
  inputs: { ared_minutes_7d: number; aerobic_minutes_7d: number; mission_day: number; horizon_days: number };
  hip_bmd: Projection & { alert: boolean };     // alert = projected median loss >= 5 %
  thigh_muscle: Projection;
  fitness_trend: Assessment["fitness_trend"];   // (new)
  source: Source;                               // (new) the projection model is trained on a simulated cohort
}
interface Projection {
  rate_pct_per_month: { q10: number; median: number; q90: number };
  estimated_loss_to_date_pct: number;
  projected_loss_pct: { q10: number; median: number; q90: number };   // at mission_day + horizon
  projected_loss_if_ared_target_met_pct: number;                       // what-if 360 min/week ARED
}
```

## `GET /api/crew/{id}/radiation`
`mission_dose_msv, career_dose_msv, career_limit_msv (600), career_used_pct, dose_rate_msv_per_day_7d,
dose_last_24h_msv, projected_career_at_mission_end_msv, projected_used_pct, spe_in_progress,
spe_event_limit_msv (250), status`, and *(new)* `spe_level (Level), dose_rate_ratio_to_7d, dose_rate_ugy_per_day,
budget_status (Level), quality_factor (3.0), reason, action, source`.

## `GET /api/indicators` *(new)* → `IndicatorCard[]`
`{ id, label, unit, body_system, hazards[], hazard_names[], data_keys[], measured_in_space, why, hazard_effect, escalate, prevention, sources }`.

## `GET /api/crew/{id}/reminders` *(new)*
`{ now, items[]: { id, label, due_at, status: "due"|"done"|"upcoming", logged_automatically }, checkin_streak_days, due_count }`.

## `GET /api/crew/{id}/reports` *(new)* → `Report[]`
One entry per alert episode that went to Earth up to `at`, newest first. Watch-level episodes of the same day share one daily report.
`{ started_at, level, condition_label, status: "sent"|"daily_report", sent_at, arrives_at, summary, items: string[] }`.

## `POST /api/assess`
Two uses. Nothing is stored.

**1. Manual check-in** *(new)*: every field of `checkin` is optional.
```json
{ "astronaut_id": "UH-04", "at": "2026-10-20T12:00:00",
  "checkin": { "systolic_bp": 128, "diastolic_bp": 82, "heart_rate": 64, "spo2": 97, "core_temp": 36.9,
               "blood_glucose_mg_dl": 92, "sleep_hours": 6.5, "mood": 3, "stress": 3, "fatigue": 3, "headache": false } }
```
Returns an `Assessment` plus `checkin_applied`. Scores are 1–5 with 5 = best.

**2. Custom hourly readings** (unchanged): minimum 6 readings, oldest first.
```json
{ "astronaut_id": "custom",
  "baseline": { "heart_rate": 62, "...": "optional, per vital" },
  "readings": [ { "timestamp": "2026-11-13T10:00:00", "heart_rate": 70, "hrv_rmssd": 48,
                  "spo2": 97.5, "resp_rate": 14, "systolic_bp": 118, "diastolic_bp": 76,
                  "core_temp": 36.9, "pvt_reaction_ms": 260, "activity_level": 0.2,
                  "is_asleep": 0, "fluid_intake_ml": 150, "cabin_co2_mmhg": 2.1,
                  "radiation_msv": 0.02, "exercise_type": "none" } ] }
```
Without a daily table only the hard limits, the cabin and the radiation parts run.
