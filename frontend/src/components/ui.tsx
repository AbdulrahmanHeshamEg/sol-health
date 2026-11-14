import type { ReactNode } from "react";
import { AlertOctagon, AlertTriangle, CheckCircle2, Database, FlaskConical, Info, PenLine, RefreshCw } from "lucide-react";
import type { Level, Source } from "../api/types";
import { NotInSnapshot } from "../api/client";
import { displayDate, parseTs, useReplay } from "../state/replay";
import { HelmetAvatar } from "./art";

export const LEVEL_WORD: Record<Level, string> = { GREEN: "Clear", YELLOW: "Heads-up", RED: "Act now" };
export const LEVEL_COLOR: Record<Level, string> = { GREEN: "var(--color-ok)", YELLOW: "var(--color-warn)", RED: "var(--color-bad)" };
export const LEVEL_SOFT: Record<Level, string> = { GREEN: "var(--color-ok-soft)", YELLOW: "var(--color-warn-soft)", RED: "var(--color-bad-soft)" };
export const LEVEL_INK: Record<Level, string> = { GREEN: "var(--color-ok-ink)", YELLOW: "var(--color-warn-ink)", RED: "var(--color-bad-ink)" };
export const WHO_LABEL = { self: "You", ground: "Your flight surgeon on Earth" } as const;

/** Status is never colour alone: each level has its own shape and word. */
export function StatusIcon({ level, size = 18 }: { level: Level; size?: number }) {
  const Icon = level === "GREEN" ? CheckCircle2 : level === "YELLOW" ? Info : AlertOctagon;
  return <Icon size={size} color={LEVEL_COLOR[level]} strokeWidth={2.3} aria-hidden="true" style={{ flex: "none" }} />;
}

export function StatusBadge({ level, size = "md", label }: { level: Level; size?: "sm" | "md" | "lg"; label?: string }) {
  const pad = size === "lg" ? "px-3 py-1.5 text-sm" : size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-[0.8rem]";
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full font-semibold ${pad}`}
      style={{ background: LEVEL_SOFT[level], color: LEVEL_INK[level] }}>
      <StatusIcon level={level} size={size === "lg" ? 16 : 14} />
      {label ?? LEVEL_WORD[level]}
    </span>
  );
}

/** Where a value comes from: a real dataset, simulated (and what it was calibrated on), or entered by you. */
export function SourceBadge({ source }: { source?: Source }) {
  if (!source) return null;
  const kind = source.kind;
  const detail = kind === "real" ? source.dataset : kind === "simulated" ? source.calibrated_on : undefined;
  const Icon = kind === "real" ? Database : kind === "entered" ? PenLine : FlaskConical;
  const style = kind === "real" ? { background: "var(--color-brand-soft)", color: "var(--color-brand-ink)" }
    : kind === "entered" ? { background: "var(--color-ink)", color: "var(--color-surface)" }
    : { background: "var(--color-surface-3)", color: "var(--color-ink-3)" };
  const word = kind === "real" ? "Real" : kind === "entered" ? "You" : "Sim";
  const title = kind === "real" ? "Real measurement" : kind === "entered" ? "You entered this value" : "Simulated";
  return (
    <span title={`${title}${detail ? `: ${detail}` : ""}`} style={style}
      className="inline-flex items-center gap-1 whitespace-nowrap rounded-md px-1.5 py-px text-[0.68rem] font-semibold uppercase tracking-wide">
      <Icon size={11} aria-hidden="true" />{word}
    </span>
  );
}

export function Card({ title, icon, aside, children, className = "", bodyClass = "card-body" }: {
  title?: ReactNode; icon?: ReactNode; aside?: ReactNode; children: ReactNode; className?: string; bodyClass?: string;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || aside) && (
        <div className="card-head flex-wrap">
          {title && <h2 className="card-title">{icon && <span className="text-ink-3" aria-hidden="true">{icon}</span>}{title}</h2>}
          {aside && <div className="text-sm text-ink-3">{aside}</div>}
        </div>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  );
}

// Avatar colours avoid green, amber and red: those mean health status here.
const PALETTE = ["#2563eb", "#64748b", "#0891b2", "#4f46e5", "#7c3aed", "#0e7490", "#db2777"];
export function Avatar({ name, size = 40, ring }: { name: string; size?: number; ring?: Level }) {
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return (
    <span className="relative inline-block shrink-0 rounded-full" style={{ width: size, height: size }} aria-hidden="true">
      <HelmetAvatar name={name} size={size} color={PALETTE[h % PALETTE.length]} />
      {ring && <span className="absolute -bottom-0.5 -right-0.5 rounded-full border-2 border-surface" style={{ width: size * 0.32, height: size * 0.32, background: LEVEL_COLOR[ring] }} />}
    </span>
  );
}

/** A ring gauge for the health score; the colour is the API's status. */
export function ScoreRing({ score, level, size = 88 }: { score: number; level: Level; size?: number }) {
  const stroke = size * 0.1, r = (size - stroke) / 2, c = 2 * Math.PI * r;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`Health score ${score} out of 100`} style={{ flex: "none" }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--color-surface-3)" strokeWidth={stroke} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={LEVEL_COLOR[level]} strokeWidth={stroke} strokeLinecap="round"
        strokeDasharray={`${(score / 100) * c} ${c}`} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" fontSize={size * 0.3} fontWeight={700} fill="var(--color-ink)" className="tnum">{score}</text>
    </svg>
  );
}

export function Skeleton({ lines = 3, height = 16 }: { lines?: number; height?: number }) {
  return (
    <div className="space-y-2.5" aria-busy="true" aria-label="Loading">
      {Array.from({ length: lines }, (_, i) => <div key={i} className="skeleton" style={{ height, width: `${94 - i * 12}%` }} />)}
    </div>
  );
}

export function ErrorNote({ error, retry }: { error: unknown; retry?: () => void }) {
  const { setAt } = useReplay();
  const text = error instanceof Error ? error.message : "Something went wrong while loading this.";
  const unsaved = error instanceof NotInSnapshot;      // retrying cannot help: offer the way out instead
  return (
    <div role="alert" className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface-2 p-4 text-sm">
      <AlertTriangle size={18} className="text-warn" aria-hidden="true" />
      <p className="flex-1">{text}</p>
      {unsaved ? <button className="btn-ghost" onClick={() => setAt(null)}>Show now</button>
        : retry && <button className="btn-ghost" onClick={retry}><RefreshCw size={14} />Try again</button>}
    </div>
  );
}

export function PageHeader({ title, subtitle, aside }: { title: string; subtitle?: ReactNode; aside?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-[1.75rem] font-bold tracking-tight sm:text-[2rem]">{title}</h1>
        {subtitle && <p className="mt-1 max-w-[72ch] text-[0.95rem] text-ink-2">{subtitle}</p>}
      </div>
      {aside && <div className="flex flex-wrap items-center gap-2">{aside}</div>}
    </div>
  );
}

/** Tabs kept in the URL (?tab=), so a link reproduces the view. */
export function Tabs<T extends string>({ tabs, value, onChange, label }: { tabs: ReadonlyArray<readonly [T, string]>; value: T; onChange: (t: T) => void; label: string }) {
  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {tabs.map(([k, text]) => <button key={k} role="tab" aria-selected={value === k} onClick={() => onChange(k)}>{text}</button>)}
    </div>
  );
}

export const fmt = (v: number | null | undefined, digits = 0) =>
  v === null || v === undefined || Number.isNaN(v) ? "–" : v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export const signed = (v: number | null | undefined, digits = 1) =>
  v === null || v === undefined ? "" : `${v > 0 ? "+" : v < 0 ? "−" : "±"}${Math.abs(v).toFixed(digits)}`;

export function when(ts: string) {
  return displayDate(ts).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" });
}
export function clock(ts: string) {
  return parseTs(ts).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "UTC" });
}
