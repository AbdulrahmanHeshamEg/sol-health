import { useMemo } from "react";
import { Area, AreaChart, CartesianGrid, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DailyRow, Level, TelemetryRow, TimelinePoint } from "../api/types";
import { displayDate } from "../state/replay";
import { LEVEL_COLOR, when } from "./ui";
import { CATEGORY, metric } from "../lib/health";

/** The colour of a reading: its category colour, grey for the cabin, blue otherwise. */
const colorOf = (key: string) => { const m = metric(key); return m ? CATEGORY[m.cat].color : key === "cabin_co2_mmhg" ? CATEGORY.cabin.color : key.startsWith("radiation") ? CATEGORY.radiation.color : "var(--color-brand)"; };

export const AXIS = { stroke: "var(--color-line)", tickLine: false, tick: { fill: "var(--color-ink-3)", fontSize: 11 } };
export const TIP = {
  contentStyle: { background: "var(--color-surface)", border: "1px solid var(--color-line)", borderRadius: 10, color: "var(--color-ink)", boxShadow: "var(--shadow-pop)", fontSize: 13 },
  labelStyle: { color: "var(--color-ink-3)", marginBottom: 2 },
  cursor: { stroke: "var(--color-line-strong)" },
};

interface Band { from: number; to: number; level: Level }

/** Consecutive hours with the same non-clear status become one shaded band. */
function bands(timeline: TimelinePoint[], index: Map<string, number>): Band[] {
  const out: Band[] = [];
  for (const p of timeline) {
    const i = index.get(p.timestamp);
    if (i === undefined || p.status === "GREEN") continue;
    const last = out[out.length - 1];
    if (last && last.level === p.status && last.to === i - 1) last.to = i; else out.push({ from: i, to: i, level: p.status });
  }
  return out;
}

function runs(rows: TelemetryRow[], test: (r: TelemetryRow) => boolean): Array<[number, number]> {
  const out: Array<[number, number]> = [];
  rows.forEach((r, i) => {
    if (!test(r)) return;
    const last = out[out.length - 1];
    if (last && last[1] === i - 1) last[1] = i; else out.push([i, i]);
  });
  return out;
}

export interface Series { key: keyof TelemetryRow; label: string; unit: string; second?: keyof TelemetryRow; limit?: number; limitLabel?: string; digits?: number }

export function Legend({ items }: { items: Array<{ color: string; label: string; opacity?: number; line?: boolean }> }) {
  return (
    <ul className="m-0 flex list-none flex-wrap gap-x-4 gap-y-1 p-0 text-xs text-ink-3">
      {items.map((it) => (
        <li key={it.label} className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" style={{ width: it.line ? 14 : 10, height: it.line ? 2.5 : 10, borderRadius: it.line ? 2 : 3, background: it.color, opacity: it.opacity ?? 1, display: "inline-block" }} />
          {it.label}
        </li>
      ))}
    </ul>
  );
}

export const STATUS_LEGEND = [
  { color: LEVEL_COLOR.YELLOW, opacity: 0.35, label: "Watch hours" },
  { color: LEVEL_COLOR.RED, opacity: 0.35, label: "Act-now hours" },
  { color: "var(--color-brand)", opacity: 0.14, label: "Asleep" },
];

/** One hourly signal with the engine's status shaded behind it. */
export function TrendChart({ rows, timeline, series, height = 220, compact = false }: {
  rows: TelemetryRow[]; timeline: TimelinePoint[]; series: Series; height?: number; compact?: boolean;
}) {
  const data = useMemo(() => rows.map((r, i) => ({ ...r, i })), [rows]);
  const index = useMemo(() => new Map(rows.map((r, i) => [r.timestamp, i])), [rows]);
  const shaded = useMemo(() => bands(timeline, index), [timeline, index]);
  const asleep = useMemo(() => runs(rows, (r) => r.is_asleep === 1), [rows]);
  const step = rows.length > 48 ? 12 : rows.length > 24 ? 6 : 3;
  const ticks = data.filter((d) => d.hour % step === 0).map((d) => d.i);
  const tick = (i: number) => {
    const r = rows[i];
    if (!r) return "";
    const d = displayDate(r.timestamp);
    return d.getUTCHours() === 0 ? d.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" }) : `${String(d.getUTCHours()).padStart(2, "0")}:00`;
  };
  const gid = `g-${String(series.key)}-${compact ? "c" : "f"}`;
  const color = colorOf(String(series.key));
  const digits = series.digits ?? 1;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: compact ? -22 : -12 }}>
        <defs>
          <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.22} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="var(--color-line)" strokeDasharray="3 4" vertical={false} />
        {asleep.map(([a, b]) => <ReferenceArea key={`s${a}`} x1={a - 0.5} x2={b + 0.5} fill="var(--color-brand)" fillOpacity={0.06} strokeOpacity={0} ifOverflow="hidden" />)}
        {shaded.map((b) => <ReferenceArea key={`b${b.from}`} x1={b.from - 0.5} x2={b.to + 0.5} fill={LEVEL_COLOR[b.level]} fillOpacity={0.14} strokeOpacity={0} ifOverflow="hidden" />)}
        {series.limit !== undefined && <ReferenceLine y={series.limit} stroke="var(--color-ink-3)" strokeDasharray="5 4" label={{ value: series.limitLabel, fill: "var(--color-ink-3)", fontSize: 10, position: "insideTopRight" }} />}
        <XAxis dataKey="i" type="number" domain={[0, Math.max(1, data.length - 1)]} ticks={ticks} tickFormatter={tick} {...AXIS} />
        <YAxis domain={["auto", "auto"]} width={52} {...AXIS} axisLine={false} tickFormatter={(v) => Number(v).toFixed(digits > 1 ? 1 : 0)} />
        <Tooltip {...TIP} labelFormatter={(i) => { const r = rows[Number(i)]; return r ? `${when(r.timestamp)} UTC` : ""; }}
          formatter={(v, name) => [`${Number(v).toFixed(digits)} ${series.unit}`, name === series.second ? "Lower" : series.second ? "Upper" : series.label]} />
        <Area dataKey={series.key as string} stroke={color} strokeWidth={2} fill={`url(#${gid})`} dot={false} isAnimationActive={false} />
        {series.second && <Area dataKey={series.second as string} stroke="#8b5cf6" strokeWidth={1.8} fill="transparent" dot={false} isAnimationActive={false} />}
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function HourlyCharts({ rows, timeline, series }: { rows: TelemetryRow[]; timeline: TimelinePoint[]; series: Series[] }) {
  return (
    <div>
      <Legend items={STATUS_LEGEND} />
      <div className="mt-4 grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
        {series.map((s) => {
          const last = rows[rows.length - 1]?.[s.key] as number | undefined;
          return (
            <figure key={String(s.key)} className="m-0 rounded-xl border border-line p-4">
              <figcaption className="flex items-baseline justify-between gap-2">
                <span className="text-sm font-semibold">{s.label}</span>
                <span className="text-xs text-ink-3"><span className="tnum text-sm font-semibold text-ink">{last !== undefined ? last.toFixed(s.digits ?? 1) : "–"}</span> {s.unit}</span>
              </figcaption>
              <TrendChart rows={rows} timeline={timeline} series={s} height={140} compact />
            </figure>
          );
        })}
      </div>
    </div>
  );
}

export interface DailySeries { key: keyof DailyRow; label: string; unit: string; domain?: [number, number] }

/** Daily indicators over the last 30 sols. A ring marks a day one of the body models flagged. */
export function DailyCharts({ rows, series }: { rows: DailyRow[]; series: DailySeries[] }) {
  const flagged = (r: DailyRow) => r.flag_spike || r.flag_drift || r.flag_combo;
  return (
    <div>
      <p className="flex items-center gap-2 text-xs text-ink-3">
        <span aria-hidden="true" style={{ display: "inline-block", width: 10, height: 10, borderRadius: 99, border: `2px solid ${LEVEL_COLOR.YELLOW}` }} />
        A day one of the body models flagged (unusual reading, slow drift or unusual combination)
      </p>
      <div className="mt-4 grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
        {series.map((s) => (
          <figure key={String(s.key)} className="m-0 rounded-xl border border-line p-4">
            <figcaption className="flex items-baseline justify-between gap-2">
              <span className="text-sm font-semibold">{s.label}</span>
              <span className="text-xs text-ink-3">{s.unit}</span>
            </figcaption>
            <ResponsiveContainer width="100%" height={140}>
              <LineChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -22 }}>
                <CartesianGrid stroke="var(--color-line)" strokeDasharray="3 4" vertical={false} />
                <XAxis dataKey="mission_day" tickFormatter={(d) => `Sol ${d}`} interval={6} {...AXIS} />
                <YAxis domain={s.domain ?? ["auto", "auto"]} width={52} allowDecimals={!s.domain} {...AXIS} axisLine={false} />
                <Tooltip {...TIP} labelFormatter={(d) => `Sol ${d}`} formatter={(v) => [`${Number(v).toFixed(1)} ${s.unit}`, s.label]} />
                <Line dataKey={s.key as string} stroke={colorOf(String(s.key))} strokeWidth={2} isAnimationActive={false}
                  dot={(p: { cx?: number; cy?: number; index?: number }) => {
                    const r = rows[p.index ?? -1];
                    return r && flagged(r) && p.cx !== undefined && p.cy !== undefined
                      ? <circle key={p.index} cx={p.cx} cy={p.cy} r={4.5} fill="var(--color-surface)" stroke={LEVEL_COLOR.YELLOW} strokeWidth={2.2} />
                      : <g key={p.index} />;
                  }} />
              </LineChart>
            </ResponsiveContainer>
          </figure>
        ))}
      </div>
    </div>
  );
}
