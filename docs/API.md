# API Reference

Base URL: `http://localhost:8000`. Interactive docs: `/docs`. All responses are JSON.
Every `GET` under `/api/crew/{id}` and `/api/crew` accepts `at=<ISO timestamp>` to replay the mission at that hour.
Real example responses: `data/demo/api_snapshots/`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness `{ "ok": true }` |
| GET | `/api/mission` | Mission info, `now`, `time_range` |
| GET | `/api/meta` | Condition ids/labels, signal names, levels |
| GET | `/api/crew` | Overview cards, sorted worst-first |
| GET | `/api/crew/{id}` | Profile (age, role, baseline, exercise plan, prior dose) |
| GET | `/api/crew/{id}/vitals?hours=72` | Raw hourly telemetry rows |
| GET | `/api/crew/{id}/assessment` | Full current assessment |
| GET | `/api/crew/{id}/timeline?hours=72` | Hour-by-hour model output |
| GET | `/api/crew/{id}/forecast?horizon_days=90` | Bone / muscle projection |
| GET | `/api/crew/{id}/radiation` | Dose vs career limit |
| POST | `/api/assess` | Assess a custom series of readings |

Errors: `404` unknown astronaut, `422` bad `at` or fewer than 24 h of history.

## `GET /api/mission`
`mission_id`, `name`, `vehicle`, `start`, `planned_duration_days` (180), `current_day` (75),
`radiation_msv_per_day_assumed`, `earth_comm_delay_s`, `note`, `now`, `time_range{start,end}`.

## `GET /api/crew` → `CrewCard[]`
```ts
type Level = "GREEN" | "YELLOW" | "RED";
interface CrewCard {
  astronaut_id: string; name: string; role: string;
  status: Level; health_score: number;          // 0..100
  condition: string; condition_label: string;
  top_alert: string | null;
  vitals: Record<VitalName, number>;            // latest values
  timestamp: string;
}
```

## `GET /api/crew/{id}/assessment` → `Assessment`
```ts
type VitalName = "heart_rate"|"hrv_rmssd"|"spo2"|"resp_rate"|"systolic_bp"|"diastolic_bp"|"core_temp"|"pvt_reaction_ms";
interface Assessment {
  astronaut_id: string; timestamp: string; mission_day: number;
  status: Level; health_score: number;
  condition: string; condition_label: string;
  probabilities: Record<string, number>;        // 7 conditions, sums to 1
  anomaly_score: number;                        // 0..1, how unusual for THIS astronaut
  alerts: Array<{
    source: "rule" | "model"; level: Level; condition: string; message: string;
    signal?: string; value?: number; threshold?: string;   // rule alerts
    probability?: number;                                   // model alerts
  }>;
  drivers: Array<{ signal: VitalName; deviation: number; unit: string; z: number }>;
  vitals: Record<VitalName, { value: number; baseline: number; delta: number; unit: string }>;
  context: { activity_level: number; is_asleep: 0|1; cabin_co2_mmhg: number;
             sleep_last_24h: number; fluid_last_24h: number;
             ared_minutes_7d: number; aerobic_minutes_7d: number };
  actions: Array<{ who: "self"|"crew"|"cmo"|"ground"; action: string;
                   condition: string; level: Level; priority: number }>;
  daily_plan: Array<{ who: "self"; category: "sleep"|"hydration"|"exercise"|"routine"; action: string }>;
  disclaimer: string;
}
```

## `GET /api/crew/{id}/vitals` → `TelemetryRow[]`
Fields: `timestamp, astronaut_id, mission_day, hour`, the 8 vitals, `activity_level, is_asleep, exercise_type
("none"|"resistive"|"aerobic"), fluid_intake_ml, cabin_co2_mmhg, radiation_msv`. See `DATA_DICTIONARY.md`.

## `GET /api/crew/{id}/timeline` → `TimelinePoint[]`
`{ timestamp, condition, p_abnormal (0..1), anomaly_score (0..1) }` — use `p_abnormal > 0.5` for chart shading.

## `GET /api/crew/{id}/forecast`
```ts
interface Forecast {
  inputs: { ared_minutes_7d: number; aerobic_minutes_7d: number; mission_day: number; horizon_days: number };
  hip_bmd: Projection & { alert: boolean };     // alert = projected median loss >= 5 %
  thigh_muscle: Projection;
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
spe_event_limit_msv (250), status`.

## `POST /api/assess`
```json
{ "astronaut_id": "custom",
  "baseline": { "heart_rate": 62, "...": "optional, per vital" },
  "readings": [ { "timestamp": "2026-11-13T10:00:00", "heart_rate": 70, "hrv_rmssd": 48,
                  "spo2": 97.5, "resp_rate": 14, "systolic_bp": 118, "diastolic_bp": 76,
                  "core_temp": 36.9, "pvt_reaction_ms": 260, "activity_level": 0.2,
                  "is_asleep": 0, "fluid_intake_ml": 150, "cabin_co2_mmhg": 2.1,
                  "radiation_msv": 0.04, "exercise_type": "none" } ] }
```
Minimum 6 readings (24+ recommended, hourly, oldest first). Without `baseline`, the median of the provided
awake resting hours is used. Returns an `Assessment`.
