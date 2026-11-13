// Types of the Sol Health API (docs/API.md). The frontend renders these; it never decides status or thresholds.

export type Level = "GREEN" | "YELLOW" | "RED";
export type VitalName =
  | "heart_rate" | "hrv_rmssd" | "spo2" | "resp_rate" | "systolic_bp" | "diastolic_bp" | "core_temp" | "pvt_reaction_ms";
export type Who = "self" | "crew" | "cmo" | "ground";

export interface Source { kind: "real" | "simulated"; dataset?: string; calibrated_on?: string }

export interface ReplayMark { id: string; label: string; at: string; show_at?: string; astronaut_id?: string }

export interface Mission {
  mission_id: string; name: string; vehicle: string; setting: string; start: string;
  planned_duration_days: number; current_day: number; radiation_msv_per_day_assumed: number;
  earth_comm_delay_s: number; note: string; now: string;
  time_range: { start: string; end: string };
  replay_marks: ReplayMark[];
  radiation_replay?: { dataset: string; from: string; to: string };
  cabin_co2_source?: { base: string; planted_high: string };
}

export interface Limits {
  cabin_co2_1h_mmhg: number; cabin_co2_7d_mmhg: number; radiation_ratio_elevated: number; radiation_ratio_shelter: number;
  career_dose_msv: number; dose_yellow_share: number; hip_bmd_loss_alert_pct: number; sleep_target_h: number;
  fluid_target_ml: number; ared_target_min_week: number; aerobic_target_min_week: number;
}

export interface Meta {
  conditions: Array<{ id: string; label: string }>;
  signals: string[]; levels: Level[];
  hazards: Record<string, string>;
  sources: Record<string, Source>;
  citations: string[];
  limits: Limits;
}

export interface CrewCard {
  astronaut_id: string; name: string; role: string; status: Level; health_score: number;
  condition: string; condition_label: string; top_alert: string | null; top_reason: string | null;
  vitals: Record<VitalName, number>; cabin_co2_mmhg: number; timestamp: string;
}

export interface Profile {
  astronaut_id: string; name: string; role: string; agency: string; age: number; sex: string; mass_kg: number;
  prior_career_dose_msv: number; ared_minutes_week: number; aerobic_minutes_week: number;
}

export interface Alert {
  source: "rule" | "model"; level: Level; condition: string; message: string; reason: string;
  kind: "hard_limit" | "spike" | "drift" | "combination" | "environmental_gate" | "spe" | "mood" | "fitness_trend";
  hazard: string; signal?: string; value?: number; threshold?: string; probability?: number; model?: string; z?: number;
}

export interface VitalReading { value: number; baseline: number; delta: number; unit: string; source: Source }
export interface IndicatorReading {
  label: string; value: number; baseline: number | null; delta: number | null; unit: string; z: number | null; date: string; source: Source;
}
export interface BodySystem {
  id: "heart" | "lungs" | "brain" | "bones_muscles" | "blood" | "immune";
  label: string; function: string; status: Level; summary: string; indicators: string[]; alerts: string[];
}
export interface Action { who: Who; action: string; condition: string; level: Level; priority: number }
export interface PlanItem { who: "self"; category: "sleep" | "hydration" | "exercise" | "routine"; action: string }
export interface FitnessTrend { alert: boolean; shift_bpm: number; weeks_ago: number; sessions: number; reason: string }

export interface Assessment {
  astronaut_id: string; timestamp: string; mission_day: number; status: Level; health_score: number;
  condition: string; condition_label: string; probabilities: Record<string, number>; anomaly_score: number;
  alerts: Alert[];
  drivers: Array<{ signal: string; deviation: number; unit: string; z: number }>;
  vitals: Record<VitalName, VitalReading>;
  indicators: Record<string, IndicatorReading>;
  body_systems: BodySystem[];
  context: {
    activity_level: number; is_asleep: 0 | 1; cabin_co2_mmhg: number; sleep_last_24h: number; fluid_last_24h: number;
    ared_minutes_7d: number; aerobic_minutes_7d: number; cabin_co2_7d_mean_mmhg: number | null; cabin_co2_high: boolean;
    radiation_ratio_to_7d: number; radiation_level: Level;
  };
  actions: Action[]; daily_plan: PlanItem[]; fitness_trend: FitnessTrend; disclaimer: string;
  checkin_applied?: Record<string, number | boolean>;
}

export interface TelemetryRow extends Record<VitalName, number> {
  timestamp: string; astronaut_id: string; mission_day: number; hour: number; activity_level: number; is_asleep: 0 | 1;
  exercise_type: "none" | "resistive" | "aerobic"; fluid_intake_ml: number; cabin_co2_mmhg: number;
  radiation_msv: number; radiation_ugy_per_day: number;
}

export interface DailyRow {
  astronaut_id: string; date: string; mission_day: number; resting_hr: number; sleep_minutes: number; sleep_hours: number;
  fatigue: number; mood: number; stress: number; headache: 0 | 1; blood_glucose_mg_dl: number;
  flag_spike: boolean; flag_drift: boolean; flag_combo: boolean;
}

export interface TimelinePoint { timestamp: string; status: Level; condition: string; p_abnormal: number; anomaly_score: number }

export interface Quantiles { q10: number; median: number; q90: number }
export interface Projection {
  rate_pct_per_month: Quantiles; estimated_loss_to_date_pct: number; projected_loss_pct: Quantiles;
  projected_loss_if_ared_target_met_pct: number;
}
export interface Forecast {
  inputs: { ared_minutes_7d: number; aerobic_minutes_7d: number; mission_day: number; horizon_days: number };
  hip_bmd: Projection & { alert: boolean }; thigh_muscle: Projection; fitness_trend: FitnessTrend | null; source: Source;
}

export interface Radiation {
  mission_dose_msv: number; career_dose_msv: number; career_limit_msv: number; career_used_pct: number;
  dose_rate_msv_per_day_7d: number; dose_last_24h_msv: number; projected_career_at_mission_end_msv: number;
  projected_used_pct: number; spe_in_progress: boolean; spe_event_limit_msv: number; status: Level; spe_level: Level;
  dose_rate_ratio_to_7d: number; dose_rate_ugy_per_day: number; budget_status: Level; quality_factor: number;
  reason: string; action: string | null; source: Source;
}

export interface IndicatorCard {
  id: string; label: string; unit: string; body_system: BodySystem["id"]; hazards: string[]; hazard_names: string[];
  data_keys: string[]; measured_in_space: string; why: string; hazard_effect: string; escalate: string; prevention: string;
  sources: Record<string, Source>;
}

export interface Reminders {
  now: string; checkin_streak_days: number; due_count: number;
  items: Array<{ id: string; label: string; due_at: string; status: "due" | "done" | "upcoming"; logged_automatically: boolean }>;
}

export interface PlantedCase {
  id: string; title: string; astronaut_id: string; affects: string; start: string; end: string; planted: string; expected: string;
}

export interface CheckIn {
  systolic_bp?: number; diastolic_bp?: number; heart_rate?: number; spo2?: number; core_temp?: number;
  blood_glucose_mg_dl?: number; sleep_hours?: number; mood?: number; stress?: number; fatigue?: number; headache?: boolean;
}
