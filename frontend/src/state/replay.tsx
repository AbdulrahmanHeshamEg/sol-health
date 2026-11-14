// Mission replay: the chosen moment lives in the URL (?at=...), so a link reproduces exactly what you see.
// With no ?at= the app shows the mission's default moment (`default_at` from /api/mission: a typical day),
// so the demo opens on an ordinary day rather than on the emergency at the end of the data.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

interface Replay {
  /** The moment every page shows: the one in the URL, else the default moment, else null (= the latest data). */
  at: string | null;
  /** True when no moment was picked, so the default moment is shown. */
  isDefault: boolean;
  /** The default moment itself (null when the mission has none). */
  defaultAt: string | null;
  /** Go to a moment; the default moment (or null) clears ?at=. */
  go: (at: string | null) => void;
  /** null goes back to the default moment. */
  setAt: (at: string | null) => void;
  playing: boolean;
  setPlaying: (on: boolean) => void;
  /** set by the layout once the mission's time range is known */
  bounds: { start: string; end: string } | null;
  setBounds: (b: { start: string; end: string }) => void;
}

const Ctx = createContext<Replay | null>(null);
const HOUR = 3600_000;

// Mission timestamps are habitat time without daylight saving. They are read as UTC so that the
// browser's own time zone can never shift a sol.
export const parseTs = (s: string) => new Date(s.replace(" ", "T").replace(/Z$/, "") + "Z");
export const toMs = (s: string) => parseTs(s).getTime();
export const toIso = (ms: number) => new Date(ms).toISOString().slice(0, 13) + ":00:00";

// Dates on screen: whatever simulated day is shown, it is labelled with today's real date, and every other date
// moves by the same number of days (yesterday stays yesterday). Times of day and sol numbers do not change.
// Only labels use this; all calculations keep the simulated timestamps.
const DAY_MS = 86_400_000;
let dateShift = 0;
function anchorDisplayTo(shown: string | null) {
  if (!shown) { dateShift = 0; return; }
  const today = new Date();
  const todayUtc = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  dateShift = todayUtc - Math.floor(toMs(shown) / DAY_MS) * DAY_MS;
}
/** The date to show for a simulated timestamp. */
export const displayDate = (s: string) => new Date(toMs(s) + dateShift);

export function ReplayProvider({ children }: { children: ReactNode }) {
  const [params, setParams] = useSearchParams();
  const picked = params.get("at");
  // The default moment comes from the mission itself (not tied to any moment, so it is fetched once).
  const mission = useQuery({ queryKey: ["mission-default"], queryFn: () => api.mission(null), staleTime: Infinity, retry: 1 });
  const fallback = mission.data?.default_at ? mission.data.default_at.replace(" ", "T") : null;
  const ready = !!picked || mission.isSuccess || mission.isError;
  const at = picked ?? fallback;
  anchorDisplayTo(at ?? mission.data?.now ?? null);
  const [playing, setPlaying] = useState(false);
  const [bounds, setBounds] = useState<Replay["bounds"]>(null);
  const atRef = useRef(at);
  atRef.current = at;

  const setAt = useCallback((next: string | null) => {
    setParams((prev) => {
      const p = new URLSearchParams(prev);
      if (next) p.set("at", next); else p.delete("at");
      return p;
    }, { replace: true });
  }, [setParams]);

  useEffect(() => {
    if (!playing || !bounds) return;
    const end = toMs(bounds.end);
    const id = window.setInterval(() => {
      const current = atRef.current ? toMs(atRef.current) : end;
      const next = current + HOUR;
      if (next >= end) { setAt(toIso(end)); setPlaying(false); } else setAt(toIso(next));
    }, 1000);                         // one mission hour per second
    return () => window.clearInterval(id);
  }, [playing, bounds, setAt]);

  const go = useCallback((next: string | null) => {
    setPlaying(false);
    setAt(next && fallback && toMs(next) === toMs(fallback) ? null : next);
  }, [setAt, fallback]);
  const value = useMemo(() => ({ at, isDefault: !picked, defaultAt: fallback, go, setAt, playing, setPlaying, bounds, setBounds }),
    [at, picked, fallback, go, setAt, playing, bounds]);
  // Wait for the default moment, so the app never flashes the latest data first.
  if (!ready) return <div className="grid min-h-screen place-items-center" aria-busy="true" aria-label="Loading"><div className="skeleton h-10 w-40" /></div>;
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useReplay(): Replay {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useReplay must be used inside ReplayProvider");
  return ctx;
}

/** Keep a picked ?at= when moving between pages (the default moment needs no parameter). */
export function useLinkWithAt() {
  const { at, isDefault } = useReplay();
  return useCallback((path: string) => (at && !isDefault ? `${path}${path.includes("?") ? "&" : "?"}at=${encodeURIComponent(at)}` : path), [at, isDefault]);
}
