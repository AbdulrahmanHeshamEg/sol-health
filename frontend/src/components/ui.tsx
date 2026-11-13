import type { ReactNode } from "react";
import type { Level, Source } from "../api/types";
import { NotInSnapshot } from "../api/client";
import { parseTs, useReplay } from "../state/replay";

export const LEVEL_WORD: Record<Level, string> = { GREEN: "Clear", YELLOW: "Watch", RED: "Act now" };
export const LEVEL_COLOR: Record<Level, string> = { GREEN: "var(--color-clear)", YELLOW: "var(--color-watch)", RED: "var(--color-act)" };
export const WHO_LABEL = { self: "You", crew: "Crew", cmo: "Crew medical officer", ground: "Flight surgeon (ground)" } as const;

/** Status is never colour alone: each level has its own shape and word. */
export function StatusIcon({ level, size = 20 }: { level: Level; size?: number }) {
  const c = LEVEL_COLOR[level];
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" style={{ flex: "none" }}>
      {level === "GREEN" && (<><circle cx="12" cy="12" r="10" fill={c} /><path d="M7 12.5l3.2 3.2L17 9" fill="none" stroke="#12251b" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" /></>)}
      {level === "YELLOW" && (<><path d="M12 2.5L22.5 21h-21z" fill={c} /><path d="M12 9v6" stroke="#2c2208" strokeWidth="2.6" strokeLinecap="round" /><circle cx="12" cy="18" r="1.4" fill="#2c2208" /></>)}
      {level === "RED" && (<><path d="M7.5 2h9L22 7.5v9L16.5 22h-9L2 16.5v-9z" fill={c} /><path d="M8 8l8 8M16 8l-8 8" stroke="#2b0f0a" strokeWidth="2.6" strokeLinecap="round" /></>)}
    </svg>
  );
}

export function StatusChip({ level, large = false }: { level: Level; large?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-2 font-bold ${large ? "text-xl" : "text-sm"}`} style={{ color: LEVEL_COLOR[level] }}>
      <StatusIcon level={level} size={large ? 30 : 20} />
      <span className="display">{LEVEL_WORD[level]}</span>
    </span>
  );
}

/** Where a value comes from: a real dataset, or simulated (and what the simulation was calibrated on). */
export function SourceBadge({ source }: { source?: Source }) {
  if (!source) return null;
  const real = source.kind === "real";
  const detail = real ? source.dataset : source.calibrated_on;
  return (
    <span title={`${real ? "Real measurement" : "Simulated"}${detail ? `: ${detail}` : ""}`}
      className="inline-flex items-center gap-1 rounded-sm px-1.5 text-xs leading-5"
      style={{ border: `1px solid ${real ? "var(--color-dusk)" : "var(--color-line)"}`, color: real ? "var(--color-dusk)" : "var(--color-dust-dim)" }}>
      <span aria-hidden="true" style={{ width: 7, height: 7, borderRadius: real ? 0 : 99, background: "currentColor", display: "inline-block" }} />
      {real ? "Real" : "Simulated"}
    </span>
  );
}

export function Panel({ title, aside, children, className = "" }: { title?: string; aside?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`panel p-5 ${className}`}>
      {(title || aside) && (
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          {title && <h2 className="text-lg">{title}</h2>}
          {aside && <div className="text-sm text-dust-dim">{aside}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export function Skeleton({ lines = 3, height = 18 }: { lines?: number; height?: number }) {
  return (
    <div className="space-y-2" aria-busy="true" aria-label="Loading">
      {Array.from({ length: lines }, (_, i) => <div key={i} className="skeleton" style={{ height, width: `${92 - i * 14}%` }} />)}
    </div>
  );
}

export function ErrorNote({ error, retry }: { error: unknown; retry?: () => void }) {
  const { setAt } = useReplay();
  const text = error instanceof Error ? error.message : "Something went wrong while loading this.";
  const unsaved = error instanceof NotInSnapshot;      // retrying cannot help: offer the way out instead
  return (
    <div role="alert" className="rounded-sm border border-line p-4 text-sm">
      <p>{text}</p>
      {unsaved ? <button className="btn-quiet mt-3" onClick={() => setAt(null)}>Show now</button>
        : retry && <button className="btn-quiet mt-3" onClick={retry}>Try again</button>}
    </div>
  );
}

export const fmt = (v: number | null | undefined, digits = 0) =>
  v === null || v === undefined || Number.isNaN(v) ? "–" : v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export const signed = (v: number | null | undefined, digits = 1) =>
  v === null || v === undefined ? "" : `${v > 0 ? "+" : v < 0 ? "−" : "±"}${Math.abs(v).toFixed(digits)}`;

export function when(ts: string) {
  return parseTs(ts).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" });
}
