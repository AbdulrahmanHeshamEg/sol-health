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
export const DAILY: DailySeries[] = [
  { key: "resting_hr", label: "Resting heart rate", unit: "bpm" },
  { key: "sleep_hours", label: "Sleep", unit: "hours" },
  { key: "mood", label: "Mood", unit: "score, 5 = best", domain: [1, 5] },
  { key: "stress", label: "Stress", unit: "score, 5 = relaxed", domain: [1, 5] },
  { key: "fatigue", label: "Energy", unit: "score, 5 = fresh", domain: [1, 5] },
  { key: "blood_glucose_mg_dl", label: "Fasting blood sugar", unit: "mg/dL" },
  { key: "urine_sg", label: "Urine concentration", unit: "specific gravity" },
  { key: "stool_bristol", label: "Stool", unit: "Bristol type, 3-5 normal", domain: [1, 7] },
];

/** Hourly chart series; limit lines come from the API. */
export const hourlySeries = (co2Limit?: number): Series[] => [
  { key: "heart_rate", label: "Heart rate", unit: "bpm" },
  { key: "spo2", label: "Blood oxygen", unit: "%" },
  { key: "core_temp", label: "Body temperature", unit: "°C" },
  { key: "systolic_bp", second: "diastolic_bp", label: "Blood pressure", unit: "mmHg" },
  { key: "resp_rate", label: "Breathing rate", unit: "per min" },
  { key: "hrv_rmssd", label: "Heart rate variability", unit: "ms" },
  { key: "pvt_reaction_ms", label: "Reaction time", unit: "ms" },
  { key: "cabin_co2_mmhg", label: "Cabin CO2", unit: "mmHg", limit: co2Limit, limitLabel: "1-hour limit" },
];

export function Gauge({ score, color }: { score: number; color: string }) {
  const r = 46, c = Math.PI * r;
  return (
    <svg width="124" height="74" viewBox="0 0 124 74" className="mx-auto block" role="img" aria-label={`Health score ${score} out of 100`}>
      <path d="M16 66a46 46 0 0192 0" fill="none" stroke="var(--color-basalt)" strokeWidth="11" strokeLinecap="round" />
      <path d="M16 66a46 46 0 0192 0" fill="none" stroke={color} strokeWidth="11" strokeLinecap="round" strokeDasharray={`${(score / 100) * c} ${c}`} />
      <text x="62" y="62" textAnchor="middle" className="numeral" fontSize="30" fill="var(--color-dust)">{score}</text>
    </svg>
  );
}

export function ActionChecklist({ actions }: { actions: Action[] }) {
  const [done, setDone] = useState<Record<string, boolean>>({});
  if (actions.length === 0) return <p className="text-base">Nothing needs doing right now. The daily plan below keeps it that way.</p>;
  const groups = (["self", "ground"] as Who[]).map((who) => [who, actions.filter((a) => a.who === who)] as const).filter(([, list]) => list.length);
  return (
    <div className="grid gap-x-8 gap-y-5 md:grid-cols-2">
      {groups.map(([who, list]) => (
        <div key={who}>
          <h3 className="text-base text-dust-dim">{WHO_LABEL[who]}</h3>
          <ul className="m-0 mt-2 list-none space-y-2 p-0">
            {list.map((a) => {
              const id = `${a.who}-${a.priority}`;
              return (
                <li key={id}>
                  <label className="flex cursor-pointer items-start gap-3 text-base">
                    <input type="checkbox" checked={!!done[id]} onChange={(e) => setDone({ ...done, [id]: e.target.checked })}
                      className="mt-1 h-5 w-5 shrink-0" style={{ accentColor: LEVEL_COLOR[a.level] }} />
                    <span style={{ textDecoration: done[id] ? "line-through" : "none", opacity: done[id] ? 0.6 : 1 }}>
                      <span className="mr-2 inline-block align-[-3px]"><StatusIcon level={a.level} size={16} /></span>{a.action}
                    </span>
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
    <li className="border-l-4 pl-4" style={{ borderColor: LEVEL_COLOR[alert.level] }}>
      <p className="display text-base">{alert.message}</p>
      <p className="max-w-[70ch] text-base">{alert.reason}</p>
      <p className="mt-1 text-sm text-dust-dim">
        {alert.source === "rule" ? "Clinical limit" : `Statistical model: ${alert.model ?? "body model"}`}
        {alert.threshold ? `, fires at ${alert.threshold}` : ""}. Hazard: {alert.hazard.toLowerCase()}.
      </p>
    </li>
  );
}

export function Readings({ a }: { a: Assessment }) {
  const flagged = new Set(a.alerts.map((x) => x.signal));
  const cells = [
    ...Object.entries(a.indicators).map(([key, r]) => ({ key, label: r.label, value: r.value, unit: r.unit, baseline: r.baseline, delta: r.delta, source: r.source,
      digits: key === "sleep_hours" ? 1 : 0, hit: flagged.has(key === "sleep_hours" ? "sleep_minutes" : key) })),
    ...Object.entries(a.vitals).map(([key, r]) => ({ key, label: VITAL_LABEL[key] ?? key, value: r.value, unit: r.unit, baseline: r.baseline, delta: r.delta, source: r.source,
      digits: key === "core_temp" ? 1 : 0, hit: flagged.has(key) })),
  ];
  return (
    <dl className="grid pl-px pt-px sm:grid-cols-2 lg:grid-cols-4">
      {cells.map((c) => (
        <div key={c.key} className="-ml-px -mt-px border border-line p-4" style={c.hit ? { boxShadow: `inset 4px 0 0 ${LEVEL_COLOR.YELLOW}` } : undefined}>
          <dt className="flex items-start justify-between gap-2 text-sm text-dust-dim"><span>{c.label}</span><SourceBadge source={c.source} /></dt>
          <dd className="mt-1"><span className="numeral text-3xl">{fmt(c.value, c.digits)}</span> <span className="text-sm text-dust-dim">{c.unit}</span></dd>
          <dd className="text-sm text-dust-dim">
            {c.baseline === null ? "No baseline yet" : `Your normal ${fmt(c.baseline, c.digits)}, ${c.delta === 0 ? "no change" : signed(c.delta, c.digits === 0 ? 0 : 1)}`}
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
    <ul className="m-0 list-none space-y-2 p-0">
      {rows.map(([id, p]) => (
        <li key={id} className="grid grid-cols-[minmax(0,14rem)_1fr_3rem] items-center gap-3 text-sm">
          <span>{labels[id] ?? id}</span>
          <span className="h-3 rounded-sm bg-basalt"><span className="block h-3 rounded-sm bg-dusk" style={{ width: `${p * 100}%` }} /></span>
          <span className="numeral text-right">{Math.round(p * 100)}%</span>
        </li>
      ))}
    </ul>
  );
}

