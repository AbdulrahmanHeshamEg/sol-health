// The sol strip: the whole mission at a glance, one column per sol and one row per crewmember,
// coloured by the worst status the engine gave that sol. It is also the replay control: pick a sol to go there.
import { useMemo } from "react";
import { Pause, Play } from "lucide-react";
import type { CrewCard, Level, Mission, ReplayMark, TimelinePoint } from "../api/types";
import { useDataMode, useMissionTimelines, useMockMarks } from "../api/hooks";
import { toIso, toMs, useReplay } from "../state/replay";
import { Avatar, LEVEL_COLOR, LEVEL_WORD, when } from "./ui";
import { Legend } from "./Charts";

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
  const { at, isDefault, go, setAt, playing, setPlaying } = useReplay();
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
    go(toIso(Math.min(noon, end)));
  };

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        {marks.map((m) => {
          const target = (m.show_at ?? m.at).replace(" ", "T");
          return (
            <button key={m.id} className="btn-ghost" aria-pressed={at !== null && toMs(target) === toMs(at)}
              onClick={() => go(target)}>
              {m.label}
            </button>
          );
        })}
        {live && (
          <button className="btn ml-auto" onClick={() => { if (!at) setAt(toIso(start + 14 * DAY)); setPlaying(!playing); }}>
            {playing ? <Pause size={15} /> : <Play size={15} />}{playing ? "Pause" : "Play replay"}
          </button>
        )}
      </div>

      <div className="mt-5 overflow-x-auto" role="group" aria-label="Your mission by sol. Each column is one sol.">
        <div className="space-y-1.5" style={{ minWidth: 640 }}>
          {rows.map((row, r) => (
            <div key={ids[r]} className="flex items-center gap-3">
              <span className="flex w-36 shrink-0 items-center gap-2 truncate text-sm" title={names[ids[r]]}>
                <Avatar name={names[ids[r]] ?? ids[r]} size={22} />
                <span className="truncate">{names[ids[r]]}</span>
              </span>
              <div className="flex flex-1 gap-[2px]">
                {row.map((level, i) => {
                  const stormNow = level === "RED" && i === total - 1 && at !== null && toMs(at) >= end - DAY;
                  return (
                    <div key={i} className={stormNow ? "storm-pulse" : undefined}
                      title={`Sol ${i + 1}: ${names[ids[r]]} ${level ? LEVEL_WORD[level].toLowerCase() : "no assessment yet"}`}
                      style={{
                        flex: 1, height: 18, borderRadius: 3,
                        background: level ? LEVEL_COLOR[level] : "var(--color-surface-3)", opacity: level === "GREEN" ? 0.35 : 1,
                        outline: i === currentSol ? "2px solid var(--color-ink)" : "none", outlineOffset: 1,
                      }} />
                  );
                })}
              </div>
            </div>
          ))}
          <div className="flex items-center gap-3 pt-2">
            <span className="w-36 shrink-0 text-xs font-medium text-ink-3">Sol {currentSol + 1}</span>
            {live ? (
              <input type="range" min={1} max={total} value={currentSol + 1} onChange={(e) => goToSol(Number(e.target.value) - 1)}
                aria-label="Mission sol" aria-valuetext={`Sol ${currentSol + 1} of ${total}`}
                className="flex-1" style={{ accentColor: "var(--color-brand)" }} />
            ) : (
              <span className="flex-1 text-xs text-ink-3">Offline, you can only open the marked moments above. Start the API to pick any sol.</span>
            )}
          </div>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <Legend items={[
          { color: LEVEL_COLOR.GREEN, opacity: 0.35, label: "Clear" },
          { color: LEVEL_COLOR.YELLOW, label: "Watch" },
          { color: LEVEL_COLOR.RED, label: "Act now" },
        ]} />
        <p className="text-xs text-ink-3">
          Showing <span className="font-medium text-ink">{at ? when(at) : `latest, ${when(mission.time_range.end)}`}{isDefault ? " (typical day, the default)" : ""}</span> · sol {currentSol + 1} of {mission.planned_duration_days}
        </p>
      </div>
    </div>
  );
}
