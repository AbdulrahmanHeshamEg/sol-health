import { useMemo } from "react";
import { CartesianGrid, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DailyRow, Level, TelemetryRow, TimelinePoint } from "../api/types";
import { parseTs } from "../state/replay";
import { LEVEL_COLOR } from "./ui";

const AXIS = { stroke: "var(--color-line)", tick: { fill: "var(--color-dust-dim)", fontSize: 12 } };
const TIP = { contentStyle: { background: "var(--color-basalt)", border: "1px solid var(--color-line)", borderRadius: 4, color: "var(--color-dust)" }, labelStyle: { color: "var(--color-dust-dim)" } };

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

export interface Series { key: keyof TelemetryRow; label: string; unit: string; second?: keyof TelemetryRow; limit?: number; limitLabel?: string }

export function HourlyCharts({ rows, timeline, series }: { rows: TelemetryRow[]; timeline: TimelinePoint[]; series: Series[] }) {
  const data = useMemo(() => rows.map((r, i) => ({ ...r, i })), [rows]);
  const index = useMemo(() => new Map(rows.map((r, i) => [r.timestamp, i])), [rows]);
  const shaded = useMemo(() => bands(timeline, index), [timeline, index]);
  const asleep = useMemo(() => runs(rows, (r) => r.is_asleep === 1), [rows]);
  const exercise = useMemo(() => runs(rows, (r) => r.exercise_type !== "none"), [rows]);
  const tick = (i: number) => {
    const r = rows[i];
    if (!r) return "";
    const d = parseTs(r.timestamp);
    return d.getUTCHours() === 0 ? d.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" }) : `${String(d.getUTCHours()).padStart(2, "0")}h`;
  };
  const ticks = data.filter((d) => d.hour % 12 === 0).map((d) => d.i);

  return (
    <div>
      <p className="mb-3 flex flex-wrap gap-x-5 gap-y-1 text-sm text-dust-dim">
        <span><Swatch color={LEVEL_COLOR.YELLOW} opacity={0.3} /> watch hours</span>
        <span><Swatch color={LEVEL_COLOR.RED} opacity={0.35} /> act-now hours</span>
        <span><Swatch color="var(--color-dusk)" opacity={0.14} /> asleep</span>
        <span><Swatch color="var(--color-dust)" opacity={0.2} /> exercise</span>
      </p>
      <div className="grid gap-x-6 gap-y-4 lg:grid-cols-2">
        {series.map((s) => (
          <figure key={String(s.key)} className="m-0">
            <figcaption className="text-sm"><span className="display">{s.label}</span> <span className="text-dust-dim">{s.unit}</span></figcaption>
            <ResponsiveContainer width="100%" height={130}>
              <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -18 }}>
                <CartesianGrid stroke="var(--color-line)" strokeOpacity={0.35} vertical={false} />
                {asleep.map(([a, b]) => <ReferenceArea key={`s${a}`} x1={a} x2={b} fill="var(--color-dusk)" fillOpacity={0.1} strokeOpacity={0} ifOverflow="hidden" />)}
                {exercise.map(([a, b]) => <ReferenceArea key={`e${a}`} x1={a - 0.4} x2={b + 0.4} fill="var(--color-dust)" fillOpacity={0.16} strokeOpacity={0} ifOverflow="hidden" />)}
                {shaded.map((b) => <ReferenceArea key={`b${b.from}`} x1={b.from - 0.5} x2={b.to + 0.5} fill={LEVEL_COLOR[b.level]} fillOpacity={b.level === "RED" ? 0.3 : 0.24} strokeOpacity={0} ifOverflow="hidden" />)}
                {s.limit !== undefined && <ReferenceLine y={s.limit} stroke="var(--color-dust-dim)" strokeDasharray="5 4" label={{ value: s.limitLabel, fill: "var(--color-dust-dim)", fontSize: 11, position: "insideTopRight" }} />}
                <XAxis dataKey="i" type="number" domain={[0, Math.max(1, data.length - 1)]} ticks={ticks} tickFormatter={tick} {...AXIS} />
                <YAxis domain={["auto", "auto"]} width={52} {...AXIS} />
                <Tooltip {...TIP} labelFormatter={(i) => rows[Number(i)]?.timestamp.slice(0, 16) ?? ""} formatter={(v) => [`${Number(v).toFixed(1)} ${s.unit}`, s.label]} />
                <Line dataKey={s.key as string} stroke="var(--color-dust)" strokeWidth={1.6} dot={false} isAnimationActive={false} />
                {s.second && <Line dataKey={s.second as string} stroke="var(--color-dusk)" strokeWidth={1.4} dot={false} isAnimationActive={false} />}
              </LineChart>
            </ResponsiveContainer>
          </figure>
        ))}
      </div>
    </div>
  );
}

function Swatch({ color, opacity }: { color: string; opacity: number }) {
  return <span aria-hidden="true" style={{ display: "inline-block", width: 14, height: 10, background: color, opacity, marginRight: 5, verticalAlign: "baseline" }} />;
}

export interface DailySeries { key: keyof DailyRow; label: string; unit: string; domain?: [number, number] }

/** Daily indicators over the last 30 sols. A ring marks a day one of the body models flagged. */
export function DailyCharts({ rows, series }: { rows: DailyRow[]; series: DailySeries[] }) {
  const flagged = (r: DailyRow) => r.flag_spike || r.flag_drift || r.flag_combo;
  return (
    <div>
      <p className="mb-3 text-sm text-dust-dim">
        <span aria-hidden="true" style={{ display: "inline-block", width: 10, height: 10, borderRadius: 99, border: `2px solid ${LEVEL_COLOR.YELLOW}`, marginRight: 6 }} />
        a day one of the body models flagged (unusual reading, slow drift or unusual combination)
      </p>
      <div className="grid gap-x-6 gap-y-4 lg:grid-cols-2">
        {series.map((s) => (
          <figure key={String(s.key)} className="m-0">
            <figcaption className="text-sm"><span className="display">{s.label}</span> <span className="text-dust-dim">{s.unit}</span></figcaption>
            <ResponsiveContainer width="100%" height={130}>
              <LineChart data={rows} margin={{ top: 6, right: 8, bottom: 0, left: -18 }}>
                <CartesianGrid stroke="var(--color-line)" strokeOpacity={0.35} vertical={false} />
                <XAxis dataKey="mission_day" tickFormatter={(d) => `sol ${d}`} interval={6} {...AXIS} />
                <YAxis domain={s.domain ?? ["auto", "auto"]} width={52} allowDecimals={!s.domain} {...AXIS} />
                <Tooltip {...TIP} labelFormatter={(d) => `Sol ${d}`} formatter={(v) => [`${Number(v).toFixed(1)} ${s.unit}`, s.label]} />
                <Line dataKey={s.key as string} stroke="var(--color-dust)" strokeWidth={1.6} isAnimationActive={false}
                  dot={(p: { cx?: number; cy?: number; index?: number }) => {
                    const r = rows[p.index ?? -1];
                    return r && flagged(r) && p.cx !== undefined && p.cy !== undefined
                      ? <circle key={p.index} cx={p.cx} cy={p.cy} r={5} fill="var(--color-hab)" stroke={LEVEL_COLOR.YELLOW} strokeWidth={2} />
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
