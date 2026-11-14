// Health-app style tiles: a metric card for each reading and a highlight card for each problem.
// Values, baselines and alerts come from the engine; these only draw them.
import { Link } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import type { Alert, Assessment, DailyRow, Level, TelemetryRow } from "../api/types";
import { CATEGORY, type CatId, type MetricDef, metric, readingOf, seriesOf, categoryOfAlert } from "../lib/health";
import { plainAlert } from "../lib/plain";
import { useLinkWithAt } from "../state/replay";
import { LEVEL_INK, SourceBadge, StatusIcon, clock, fmt, signed } from "./ui";

/** A small line: the shape of the last day or two weeks. An optional dashed line marks your normal. */
export function Sparkline({ values, color, width = 110, height = 40, baseline, fluid = false }: { values: number[]; color: string; width?: number; height?: number; baseline?: number | null; fluid?: boolean }) {
  const v = values.filter((x) => Number.isFinite(x));
  if (v.length < 2) return <svg width={width} height={height} aria-hidden="true" />;
  const all = baseline != null ? [...v, baseline] : v;
  const lo = Math.min(...all), hi = Math.max(...all), span = hi - lo || 1, pad = 4;
  const x = (i: number) => pad + (i / (v.length - 1)) * (width - pad * 2);
  const y = (n: number) => pad + (1 - (n - lo) / span) * (height - pad * 2);
  const d = v.map((n, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(n).toFixed(1)}`).join("");
  return (
    <svg width={fluid ? "100%" : width} height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio={fluid ? "none" : undefined} aria-hidden="true" style={{ flex: "none", overflow: "visible", display: "block" }}>
      {baseline != null && <line x1={pad} x2={width - pad} y1={y(baseline)} y2={y(baseline)} stroke="var(--color-ink-3)" strokeDasharray="3 3" strokeWidth={1} opacity={0.6} />}
      <path d={d} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      {!fluid && <circle cx={x(v.length - 1)} cy={y(v[v.length - 1])} r={3.5} fill={color} stroke="var(--color-surface)" strokeWidth={1.5} />}
    </svg>
  );
}

export function CategoryLabel({ cat, label }: { cat: CatId; label?: string }) {
  const c = CATEGORY[cat];
  const Icon = c.icon;
  return (
    <span className="inline-flex items-center gap-1.5 text-[0.9rem] font-semibold" style={{ color: c.color }}>
      <Icon size={16} fill={cat === "heart" ? c.color : "none"} strokeWidth={2.2} aria-hidden="true" />{label ?? c.label}
    </span>
  );
}

const valueText = (m: MetricDef, value: number, second?: number) =>
  m.second && second !== undefined ? `${fmt(value)}/${fmt(second)}` : fmt(value, m.digits);

/** One reading, laid out like a health-app summary tile. */
export function MetricCard({ m, a, hourly, daily, to }: { m: MetricDef; a: Assessment; hourly?: TelemetryRow[]; daily?: DailyRow[]; to?: string }) {
  const link = useLinkWithAt();
  const r = readingOf(a, m);
  if (!r) return null;
  const alert = a.alerts.find((x) => x.signal === m.key || (m.key === "sleep_hours" && x.signal === "sleep_minutes"));
  const color = CATEGORY[m.cat].color;
  const word = m.words?.[Math.round(r.value)];
  const time = m.series.kind === "daily" ? "Today" : clock(a.timestamp);
  const body = (
    <>
      <div className="flex items-center justify-between gap-2">
        <CategoryLabel cat={m.cat} label={m.label} />
        <span className="flex items-center gap-0.5 text-xs text-ink-3">{time}<ChevronRight size={14} aria-hidden="true" /></span>
      </div>
      <div className="mt-3 flex items-end justify-between gap-3">
        <p className="min-w-0 leading-none">
          {word
            ? <span className="text-[1.6rem] font-bold tracking-tight">{word}</span>
            : <><span className="tnum whitespace-nowrap text-[1.9rem] font-bold tracking-tight">{valueText(m, r.value, r.second)}</span> <span className="text-[0.95rem] font-semibold text-ink-3">{m.unit}</span></>}
        </p>
        <Sparkline values={seriesOf(m, hourly, daily)} color={color} baseline={r.baseline} width={88} height={34} />
      </div>
      <p className="mt-2.5 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-xs text-ink-3">
        {alert
          ? <span className="inline-flex items-center gap-1 font-semibold" style={{ color: LEVEL_INK[alert.level] }}><StatusIcon level={alert.level} size={13} />Outside your normal</span>
          : r.baseline !== null ? <span className="tnum">Your normal {word ? m.words?.[Math.round(r.baseline)] ?? fmt(r.baseline) : fmt(r.baseline, m.digits)}{r.delta ? ` (${signed(r.delta, m.digits)})` : ""}</span> : <span>No normal yet</span>}
        <SourceBadge source={r.source} />
      </p>
    </>
  );
  return to
    ? <Link to={link(to)} className="card block p-4 text-ink no-underline transition-transform hover:scale-[1.01]">{body}</Link>
    : <div className="card p-4">{body}</div>;
}

/** A problem, shown the way a health app shows a highlight: the category, one plain sentence, the reason, and its trend. */
export function HighlightCard({ alert, hourly, daily, stamp }: { alert: Alert; hourly?: TelemetryRow[]; daily?: DailyRow[]; stamp: string }) {
  const cat = categoryOfAlert(alert);
  const plain = plainAlert(alert);
  const m = alert.signal ? metric(alert.signal === "sleep_minutes" ? "sleep_hours" : alert.signal) : undefined;
  const values = m ? seriesOf(m, hourly, daily) : alert.signal === "cabin_co2_mmhg" ? (hourly ?? []).slice(-24).map((r) => r.cabin_co2_mmhg) : [];
  return (
    <article className="card p-4">
      <div className="flex items-center justify-between gap-2">
        <CategoryLabel cat={cat} />
        <span className="text-xs text-ink-3">{stamp}</span>
      </div>
      <h3 className="mt-2.5 flex items-start gap-2 text-[1.05rem] font-bold leading-snug">
        <StatusIcon level={alert.level as Level} size={18} />{plain.title}
      </h3>
      <p className="mt-1 text-sm text-ink-2">{plain.body}</p>
      {values.length > 1 && (
        <div className="mt-3 rounded-xl bg-surface-2 px-3 py-2">
          <Sparkline values={values} color={CATEGORY[cat].color} width={300} height={56} fluid />
          <p className="mt-1 text-[0.7rem] text-ink-3">{m?.series.kind === "daily" ? "Last 14 days" : "Last 24 hours"}</p>
        </div>
      )}
      <details className="mt-3 text-xs text-ink-3">
        <summary className="cursor-pointer font-medium">More detail</summary>
        <p className="mt-1.5">{alert.message}. {alert.reason}</p>
      </details>
    </article>
  );
}
