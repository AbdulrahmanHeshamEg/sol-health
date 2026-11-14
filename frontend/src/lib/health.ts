// How readings are grouped and drawn, in the manner of a phone health app: each reading belongs to a category
// with its own colour and icon. Display only: values, baselines and alerts all come from the engine.
import { Atom, Brain, Eye, FlaskConical, Heart, Moon, Thermometer, Wind, House, type LucideIcon } from "lucide-react";
import type { Alert, Assessment, DailyRow, TelemetryRow } from "../api/types";

export type CatId = "heart" | "respiratory" | "body" | "sleep" | "mind" | "labs" | "eyes" | "cabin" | "radiation";
export const CATEGORY: Record<CatId, { label: string; color: string; icon: LucideIcon }> = {
  heart: { label: "Heart", color: "#ff2d55", icon: Heart },
  respiratory: { label: "Respiratory", color: "#32ade6", icon: Wind },
  body: { label: "Body temperature", color: "#af52de", icon: Thermometer },
  sleep: { label: "Sleep", color: "#5e5ce6", icon: Moon },
  mind: { label: "Mind", color: "#30b0c7", icon: Brain },
  labs: { label: "Lab tests", color: "#ff9500", icon: FlaskConical },
  eyes: { label: "Eyes", color: "#a2845e", icon: Eye },
  cabin: { label: "Cabin air", color: "#8e8e93", icon: House },
  radiation: { label: "Radiation", color: "#ffb800", icon: Atom },
};

type Series = { kind: "hourly"; key: keyof TelemetryRow } | { kind: "daily"; key: keyof DailyRow };
export interface MetricDef {
  key: string; label: string; cat: CatId; unit: string; digits: number; from: "vital" | "indicator";
  series: Series; second?: string; words?: Record<number, string>;
}

const MOOD = { 1: "Very low", 2: "Low", 3: "Okay", 4: "Good", 5: "Very good" };
const STRESS = { 1: "Very stressed", 2: "Stressed", 3: "Normal", 4: "Calm", 5: "Very relaxed" };
const ENERGY = { 1: "Exhausted", 2: "Tired", 3: "Normal", 4: "Fresh", 5: "Very fresh" };

export const METRICS: MetricDef[] = [
  { key: "heart_rate", label: "Heart Rate", cat: "heart", unit: "BPM", digits: 0, from: "vital", series: { kind: "hourly", key: "heart_rate" } },
  { key: "resting_hr", label: "Resting Heart Rate", cat: "heart", unit: "BPM", digits: 0, from: "indicator", series: { kind: "daily", key: "resting_hr" } },
  { key: "hrv_rmssd", label: "Heart Rate Variability", cat: "heart", unit: "ms", digits: 0, from: "vital", series: { kind: "hourly", key: "hrv_rmssd" } },
  { key: "systolic_bp", second: "diastolic_bp", label: "Blood Pressure", cat: "heart", unit: "mmHg", digits: 0, from: "vital", series: { kind: "hourly", key: "systolic_bp" } },
  { key: "spo2", label: "Blood Oxygen", cat: "respiratory", unit: "%", digits: 0, from: "vital", series: { kind: "hourly", key: "spo2" } },
  { key: "resp_rate", label: "Respiratory Rate", cat: "respiratory", unit: "breaths/min", digits: 0, from: "vital", series: { kind: "hourly", key: "resp_rate" } },
  { key: "core_temp", label: "Body Temperature", cat: "body", unit: "°C", digits: 1, from: "vital", series: { kind: "hourly", key: "core_temp" } },
  { key: "sleep_hours", label: "Sleep", cat: "sleep", unit: "hr", digits: 1, from: "indicator", series: { kind: "daily", key: "sleep_hours" } },
  { key: "mood", label: "Mood", cat: "mind", unit: "of 5", digits: 0, from: "indicator", series: { kind: "daily", key: "mood" }, words: MOOD },
  { key: "stress", label: "Stress", cat: "mind", unit: "of 5", digits: 0, from: "indicator", series: { kind: "daily", key: "stress" }, words: STRESS },
  { key: "fatigue", label: "Energy", cat: "mind", unit: "of 5", digits: 0, from: "indicator", series: { kind: "daily", key: "fatigue" }, words: ENERGY },
  { key: "pvt_reaction_ms", label: "Reaction Time", cat: "mind", unit: "ms", digits: 0, from: "vital", series: { kind: "hourly", key: "pvt_reaction_ms" } },
  { key: "blood_glucose_mg_dl", label: "Blood Glucose", cat: "labs", unit: "mg/dL", digits: 0, from: "indicator", series: { kind: "daily", key: "blood_glucose_mg_dl" } },
];
export const metric = (key: string) => METRICS.find((m) => m.key === key);

/** The reading for a metric in an assessment, or undefined when the engine did not report it. */
export function readingOf(a: Assessment, m: MetricDef) {
  const r = m.from === "vital" ? a.vitals[m.key as keyof Assessment["vitals"]] : a.indicators[m.key];
  if (!r) return undefined;
  const second = m.second ? a.vitals[m.second as keyof Assessment["vitals"]] : undefined;
  return { value: r.value, baseline: r.baseline, delta: r.delta, source: r.source, second: second?.value };
}

/** Series values for a sparkline: the last 24 hours, or the last 14 days. */
export function seriesOf(m: MetricDef, hourly?: TelemetryRow[], daily?: DailyRow[]): number[] {
  if (m.series.kind === "hourly") return (hourly ?? []).slice(-24).map((r) => Number(r[m.series.key as keyof TelemetryRow]));
  return (daily ?? []).slice(-14).map((r) => Number(r[m.series.key as keyof DailyRow]));
}

/** Which category an alert belongs to, for colour and icon. */
export function categoryOfAlert(a: Alert): CatId {
  if (a.kind === "spe") return "radiation";
  if (a.kind === "eye_exam" || a.condition === "optic_disc_change") return "eyes";
  if (a.kind === "environmental_gate" || a.signal === "cabin_co2_mmhg") return "cabin";
  const m = a.signal ? metric(a.signal === "sleep_minutes" ? "sleep_hours" : a.signal) : undefined;
  if (m) return m.cat;
  if (a.kind === "mood" || a.kind === "combination") return "mind";
  return "heart";
}
