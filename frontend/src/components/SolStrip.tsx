// The sol strip: the whole mission at a glance, one column per sol and one row per crewmember,
// coloured by the worst status the engine gave that sol. It is also the replay control: pick a sol to go there.
import { useMemo } from "react";
import type { CrewCard, Level, Mission, ReplayMark, TimelinePoint } from "../api/types";
import { useDataMode, useMissionTimelines, useMockMarks } from "../api/hooks";
import { toIso, toMs, useReplay } from "../state/replay";
import { LEVEL_COLOR, LEVEL_WORD, when } from "./ui";

const RANK: Record<Level, number> = { GREEN: 0, YELLOW: 1, RED: 2 };
const DAY = 86_400_000;

function perSol(points: TimelinePoint[] | undefined, start: number, sols: number): (Level | null)[] {
  const out: (Level | null)[] = Array(sols).fill(null);
  for (const p of points ?? []) {
    const i = Math.floor((toMs(p.timestamp) - start) / DAY);
    if (i >= 0 && i < sols && (out[i] === null || RANK[p.status] > RANK[out[i]!])) out[i] = p.status;
  }
  return out;
}

export function SolStrip({ mission, crew }: { mission: Mission; crew: CrewCard[] }) {
  const { at, setAt, playing, setPlaying } = useReplay();
  const mode = useDataMode();
  const ids = useMemo(() => crew.map((c) => c.astronaut_id).sort(), [crew]);
  const timelines = useMissionTimelines(ids);
  const mockMarks = useMockMarks();
  const start = toMs(mission.time_range.start);
  const end = toMs(mission.time_range.end);
  const total = Math.max(mission.current_day, Math.ceil((end - start + 3600_000) / DAY));
  const rows = timelines.map((t) => perSol(t.data, start, total));
  const names = Object.fromEntries(crew.map((c) => [c.astronaut_id, c.name]));
  const nowMs = at ? toMs(at) : end;
  const currentSol = Math.min(total - 1, Math.floor((nowMs - start) / DAY));
  const marks: ReplayMark[] = mode === "mock" ? (mockMarks.data ?? []) : mission.replay_marks;
  const live = mode === "live";

  const goToSol = (i: number) => {
    const noon = start + i * DAY + 12 * 3600_000;
    setAt(noon >= end ? null : toIso(noon));
  };

  return (
    <div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm">
        <span className="text-dust-dim">Jump to</span>
        {marks.map((m) => {
          const target = (m.show_at ?? m.at).replace(" ", "T");
          return (
            <button key={m.id} className="btn-quiet" aria-pressed={at !== null && toMs(target) === toMs(at)}
              onClick={() => { setPlaying(false); setAt(target); }}>
              {m.label}
            </button>
          );
        })}
        <button className="btn-quiet" aria-pressed={at === null} onClick={() => { setPlaying(false); setAt(null); }}>Now</button>
        {live && (
          <button className="btn-quiet" aria-pressed={playing} onClick={() => { if (!at) setAt(toIso(start + 14 * DAY)); setPlaying(!playing); }}>
            {playing ? "Pause replay" : "Play replay"}
          </button>
        )}
      </div>

      <div className="mt-3 overflow-x-auto" role="group" aria-label="Mission timeline by sol. Each row is a crewmember, each column a sol.">
        <div style={{ minWidth: 640 }}>
          {rows.map((row, r) => (
            <div key={ids[r]} className="flex items-center gap-2" style={{ height: 15 }}>
              <span className="w-24 shrink-0 truncate text-xs text-dust-dim" title={names[ids[r]]}>{names[ids[r]]?.split(" ")[0]}</span>
              <div className="flex flex-1 gap-px">
                {row.map((level, i) => {
                  const stormNow = level === "RED" && i === total - 1 && at === null;
                  return (
                    <div key={i} className={stormNow ? "storm-pulse" : undefined}
                      title={`Sol ${i + 1}: ${names[ids[r]]} ${level ? LEVEL_WORD[level].toLowerCase() : "no assessment yet"}`}
                      style={{ flex: 1, height: 11, background: level ? LEVEL_COLOR[level] : "var(--color-hab-raised)", opacity: level === "GREEN" ? 0.42 : 1,
                        outline: i === currentSol ? "2px solid var(--color-dust)" : "none", outlineOffset: 1 }} />
                  );
                })}
              </div>
            </div>
          ))}
          <div className="flex items-center gap-2">
            <span className="w-24 shrink-0 text-xs text-dust-dim">Sol</span>
            {live ? (
              <input type="range" min={1} max={total} value={currentSol + 1} onChange={(e) => goToSol(Number(e.target.value) - 1)}
                aria-label="Mission sol" aria-valuetext={`Sol ${currentSol + 1} of ${total}`}
                className="flex-1" style={{ accentColor: "var(--color-dusk)" }} />
            ) : (
              <span className="flex-1 text-xs text-dust-dim">Offline snapshot: use the marked moments above. Start the API to scrub freely.</span>
            )}
          </div>
        </div>
      </div>
      <p className="mt-1 text-xs text-dust-dim">
        Showing <span className="text-dust">{at ? when(at) : `now, ${when(mission.time_range.end)}`}</span>, sol {currentSol + 1} of {mission.planned_duration_days}.
        Dim green is clear; amber is watch; red is act now.
      </p>
    </div>
  );
}
