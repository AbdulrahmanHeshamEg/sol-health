// Mission replay: the chosen moment lives in the URL (?at=...), so a link reproduces exactly what you see.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

interface Replay {
  at: string | null;                 // null = now
  setAt: (at: string | null) => void;
  playing: boolean;
  setPlaying: (on: boolean) => void;
  /** set by the header once the mission's time range is known */
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

export function ReplayProvider({ children }: { children: ReactNode }) {
  const [params, setParams] = useSearchParams();
  const at = params.get("at");
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
      if (next >= end) { setAt(null); setPlaying(false); } else setAt(toIso(next));
    }, 1000);                         // one mission hour per second
    return () => window.clearInterval(id);
  }, [playing, bounds, setAt]);

  const value = useMemo(() => ({ at, setAt, playing, setPlaying, bounds, setBounds }), [at, setAt, playing, bounds]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useReplay(): Replay {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useReplay must be used inside ReplayProvider");
  return ctx;
}

/** Keep ?at= when moving between pages. */
export function useLinkWithAt() {
  const { at } = useReplay();
  return useCallback((path: string) => (at ? `${path}?at=${encodeURIComponent(at)}` : path), [at]);
}
