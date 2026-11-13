// Clickable body figure: six body systems, each coloured by the status the engine gave it.
// Shapes differ per system and the list beside the figure repeats every status in words, so colour is never the only cue.
import { useState } from "react";
import { Link } from "react-router-dom";
import type { BodySystem, IndicatorCard } from "../api/types";
import { useLinkWithAt } from "../state/replay";
import { LEVEL_COLOR, LEVEL_WORD, StatusIcon } from "./ui";

type Id = BodySystem["id"];

// Where each system sits on the 200 x 420 figure.
const SPOT: Record<Id, { cx: number; cy: number; shape: React.ReactNode }> = {
  brain: { cx: 100, cy: 40, shape: <path d="M82 40c0-14 9-22 18-22s18 8 18 22c0 9-5 14-9 16h-18c-4-2-9-7-9-16z" /> },
  lungs: { cx: 100, cy: 128, shape: <><path d="M94 104c-12 2-20 14-20 34 0 8 3 12 8 12 8 0 12-8 12-18z" /><path d="M106 104c12 2 20 14 20 34 0 8-3 12-8 12-8 0-12-8-12-18z" /></> },
  heart: { cx: 104, cy: 136, shape: <path d="M106 150c-10-7-15-12-15-18 0-5 4-8 8-8 3 0 5 1 7 4 2-3 4-4 7-4 4 0 8 3 8 8 0 6-5 11-15 18z" /> },
  immune: { cx: 100, cy: 84, shape: <path d="M100 72l13 5v9c0 8-6 13-13 16-7-3-13-8-13-16v-9z" /> },
  blood: { cx: 100, cy: 196, shape: <path d="M100 176c7 9 11 15 11 21a11 11 0 01-22 0c0-6 4-12 11-21z" /> },
  bones_muscles: { cx: 80, cy: 318, shape: <><rect x="71" y="266" width="15" height="96" rx="7" /><rect x="114" y="266" width="15" height="96" rx="7" /></> },
};
const ORDER: Id[] = ["brain", "immune", "lungs", "heart", "blood", "bones_muscles"];

export function BodyFigure({ systems, cards }: { systems: BodySystem[]; cards?: IndicatorCard[] }) {
  const worst = [...systems].sort((a, b) => "GYR".indexOf(b.status[0]) - "GYR".indexOf(a.status[0]))[0];
  const [picked, setPicked] = useState<Id | null>(null);
  const link = useLinkWithAt();
  const byId = Object.fromEntries(systems.map((s) => [s.id, s])) as Record<Id, BodySystem>;
  const current = byId[picked ?? worst.id];
  const related = (cards ?? []).filter((c) => c.body_system === current.id);

  return (
    <div className="grid gap-5 sm:grid-cols-[210px_1fr]">
      <svg viewBox="0 0 200 420" className="mx-auto w-full max-w-[210px]" role="group" aria-label="Body systems. Select one to read its status.">
        <g fill="var(--color-hab-raised)" stroke="var(--color-line)" strokeWidth="1.5">
          <circle cx="100" cy="38" r="27" />
          <path d="M62 78c0-8 6-14 14-14h48c8 0 14 6 14 14l10 104c1 7-9 9-11 2l-9-58v96l6 168c0 10-18 10-19 0l-12-150h-6L85 390c-1 10-19 10-19 0l6-168v-96l-9 58c-2 7-12 5-11-2z" />
        </g>
        {ORDER.map((id) => {
          const s = byId[id];
          if (!s) return null;
          const on = current.id === id;
          return (
            <g key={id} role="button" tabIndex={0} aria-pressed={on} aria-label={`${s.label}: ${LEVEL_WORD[s.status]}`}
              onClick={() => setPicked(id)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setPicked(id); } }}
              style={{ cursor: "pointer", outline: "none" }}
              fill={LEVEL_COLOR[s.status]} fillOpacity={s.status === "GREEN" ? 0.55 : 1}
              stroke={on ? "var(--color-dust)" : "var(--color-basalt)"} strokeWidth={on ? 3 : 1.5} strokeLinejoin="round">
              {SPOT[id].shape}
            </g>
          );
        })}
      </svg>

      <div>
        <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
          {ORDER.map((id) => byId[id] && (
            <li key={id}>
              <button className="btn-quiet inline-flex items-center gap-2 text-sm" aria-pressed={current.id === id} onClick={() => setPicked(id)}>
                <StatusIcon level={byId[id].status} size={16} /> {byId[id].label}
              </button>
            </li>
          ))}
        </ul>
        <div className="mt-4" aria-live="polite">
          <h3 className="text-lg" style={{ color: LEVEL_COLOR[current.status] }}>{current.label}: {LEVEL_WORD[current.status].toLowerCase()}</h3>
          <p className="mt-1 max-w-[60ch] text-base">{current.summary}</p>
          <p className="mt-2 max-w-[60ch] text-sm text-dust-dim">{current.function}</p>
          {related.length > 0 && (
            <p className="mt-3 text-sm">
              Why we measure it:{" "}
              {related.map((c, i) => (
                <span key={c.id}>{i > 0 && ", "}<Link to={`${link("/learn")}#${c.id}`}>{c.label.toLowerCase()}</Link></span>
              ))}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
