// Building blocks of the personal pages: actions, alerts, readings, evidence and chart series.
import { useState } from "react";
import { useMeta } from "../api/hooks";
import type { Action, Alert, Assessment, Who } from "../api/types";
import type { DailySeries, Series } from "./Charts";
import { LEVEL_COLOR, SourceBadge, StatusIcon, WHO_LABEL, fmt, signed } from "./ui";

export const VITAL_LABEL: Record<string, string> = {
  heart_rate: "Heart rate", hrv_rmssd: "Heart rate variability", spo2: "Blood oxygen", resp_rate: "Breathing rate",
  systolic_bp: "Blood pressure, upper", diastolic_bp: "Blood pressure, lower", core_temp: "Body temperature", pvt_reaction_ms: "Reaction time",
};
/** The API writes "C"; show the degree sign. */
export const unitLabel = (u: string) => (u === "C" ? "°C" : u);

export const DAILY: DailySeries[] = [
  { key: "resting_hr", label: "Resting heart rate", unit: "bpm" },
  { key: "sleep_hours", label: "Sleep", unit: "hours" },
  { key: "mood", label: "Mood", unit: "1 to 5, 5 is best", domain: [1, 5] },
  { key: "stress", label: "Stress", unit: "1 to 5, 5 is relaxed", domain: [1, 5] },
  { key: "fatigue", label: "Energy", unit: "1 to 5, 5 is fresh", domain: [1, 5] },
  { key: "blood_glucose_mg_dl", label: "Fasting blood sugar", unit: "mg/dL" },
  { key: "urine_sg", label: "Urine concentration", unit: "specific gravity" },
  { key: "stool_bristol", label: "Stool", unit: "Bristol type, 3 to 5 is normal", domain: [1, 7] },
];

/** Hourly chart series; limit lines come from the API. */
export const hourlySeries = (co2Limit?: number): Series[] => [
  { key: "heart_rate", label: "Heart rate", unit: "bpm", digits: 0 },
  { key: "spo2", label: "Blood oxygen", unit: "%", digits: 1 },
  { key: "core_temp", label: "Body temperature", unit: "°C", digits: 2 },
  { key: "systolic_bp", second: "diastolic_bp", label: "Blood pressure", unit: "mmHg", digits: 0 },
  { key: "resp_rate", label: "Breathing rate", unit: "per min", digits: 1 },
  { key: "hrv_rmssd", label: "Heart rate variability", unit: "ms", digits: 0 },
  { key: "pvt_reaction_ms", label: "Reaction time", unit: "ms", digits: 0 },
  { key: "cabin_co2_mmhg", label: "Cabin CO2", unit: "mmHg", limit: co2Limit, limitLabel: "1-hour limit", digits: 2 },
];

export function ActionChecklist({ actions }: { actions: Action[] }) {
  const [done, setDone] = useState<Record<string, boolean>>({});
  if (actions.length === 0) return <p className="text-sm text-ink-2">Nothing to do right now.</p>;
  const groups = (["self", "ground"] as Who[]).map((who) => [who, actions.filter((a) => a.who === who)] as const).filter(([, list]) => list.length);
  return (
    <div className="grid gap-x-6 gap-y-5 md:grid-cols-2">
      {groups.map(([who, list]) => (
        <div key={who}>
          <p className="eyebrow">{WHO_LABEL[who]}</p>
          <ul className="m-0 mt-2 list-none space-y-1.5 p-0">
            {list.map((a) => {
              const id = `${a.who}-${a.priority}`;
              return (
                <li key={id}>
                  <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-line p-3 text-sm transition-colors hover:bg-surface-2"
                    style={done[id] ? { opacity: 0.6 } : undefined}>
                    <input type="checkbox" checked={!!done[id]} onChange={(e) => setDone({ ...done, [id]: e.target.checked })}
                      className="mt-0.5 h-[18px] w-[18px] shrink-0" style={{ accentColor: "var(--color-brand)" }} />
                    <span className="flex-1" style={{ textDecoration: done[id] ? "line-through" : "none" }}>{a.action}</span>
                    <StatusIcon level={a.level} size={16} />
                  </label>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}

export function AlertItem({ alert }: { alert: Alert }) {
  return (
    <li className="rounded-xl border-l-[3px] bg-surface-2 p-4" style={{ borderColor: LEVEL_COLOR[alert.level] }}>
      <p className="font-semibold">{alert.message}</p>
      <p className="mt-1 text-sm text-ink-2">{alert.reason}</p>
      <p className="mt-2 text-xs text-ink-3">
        {alert.source === "rule" ? "Clinical limit" : `Statistical model: ${alert.model ?? "body model"}`}
        {alert.threshold ? ` · fires at ${alert.threshold}` : ""} · Hazard: {alert.hazard.toLowerCase()}
      </p>
    </li>
  );
}

export function Readings({ a }: { a: Assessment }) {
  const flagged = new Set(a.alerts.map((x) => x.signal));
  const cells = [
    ...Object.entries(a.vitals).map(([key, r]) => ({ key, label: VITAL_LABEL[key] ?? key, value: r.value, unit: unitLabel(r.unit), baseline: r.baseline, delta: r.delta, source: r.source,
      digits: key === "core_temp" ? 1 : 0, hit: flagged.has(key) })),
    ...Object.entries(a.indicators).map(([key, r]) => ({ key, label: r.label, value: r.value, unit: unitLabel(r.unit), baseline: r.baseline, delta: r.delta, source: r.source,
      digits: key === "sleep_hours" ? 1 : key === "urine_sg" ? 3 : 0, hit: flagged.has(key === "sleep_hours" ? "sleep_minutes" : key) })),
  ];
  return (
    <dl className="m-0 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
      {cells.map((c) => (
        <div key={c.key} className="rounded-xl border p-4"
          style={c.hit ? { borderColor: "var(--color-warn)", background: "var(--color-warn-soft)" } : { borderColor: "var(--color-line)" }}>
          <dt className="flex items-start justify-between gap-2 text-sm text-ink-2"><span>{c.label}</span><SourceBadge source={c.source} /></dt>
          <dd className="m-0 mt-2"><span className="tnum text-2xl font-bold">{fmt(c.value, c.digits)}</span> <span className="text-sm text-ink-3">{c.unit}</span></dd>
          <dd className="m-0 mt-1 text-xs text-ink-3">
            {c.baseline === null ? "No baseline yet" : <>Your normal <span className="tnum">{fmt(c.baseline, c.digits)}</span> · <span className="tnum font-medium text-ink-2">{c.delta === 0 ? "no change" : signed(c.delta, c.digits)}</span></>}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function Evidence({ a }: { a: Assessment }) {
  const meta = useMeta();
  const labels = Object.fromEntries((meta.data?.conditions ?? []).map((c) => [c.id, c.label]));
  const rows = Object.entries(a.probabilities).filter(([, p]) => p > 0.001).sort((x, y) => y[1] - x[1]);
  return (
    <ul className="m-0 list-none space-y-2.5 p-0">
      {rows.map(([id, p]) => (
        <li key={id} className="text-sm">
          <div className="flex justify-between gap-3"><span>{labels[id] ?? id}</span><span className="tnum font-semibold">{Math.round(p * 100)}%</span></div>
          <div className="mt-1 h-1.5 rounded-full bg-surface-3"><div className="h-full rounded-full bg-brand" style={{ width: `${p * 100}%` }} /></div>
        </li>
      ))}
    </ul>
  );
}
