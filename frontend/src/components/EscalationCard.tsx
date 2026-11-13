// What your flight surgeon on Earth hears about right now. The engine decides: RED is sent at once,
// YELLOW goes in the daily report, nothing is sent when you are clear.
import { Link } from "react-router-dom";
import type { Escalation } from "../api/types";
import { useLinkWithAt } from "../state/replay";
import { LEVEL_COLOR, when } from "./ui";

const HEADLINE = { sent: "Sent to your flight surgeon", daily_report: "In tonight's report to your flight surgeon", none: "Your flight surgeon" } as const;

export function EscalationCard({ escalation }: { escalation: Escalation }) {
  const link = useLinkWithAt();
  const e = escalation;
  const color = e.status === "none" ? "var(--color-line)" : LEVEL_COLOR[e.level];
  return (
    <section className="panel flex flex-wrap items-start gap-x-6 gap-y-2 p-5" style={{ borderLeft: `6px solid ${color}` }} aria-live="polite">
      <svg width="34" height="34" viewBox="0 0 24 24" aria-hidden="true" style={{ flex: "none", marginTop: 2 }}>
        <circle cx="12" cy="12" r="10" fill="none" stroke="var(--color-dusk)" strokeWidth="1.6" />
        <path d="M4 12h16M12 2c3 3 3 17 0 20M12 2c-3 3-3 17 0 20" fill="none" stroke="var(--color-dusk)" strokeWidth="1.2" />
      </svg>
      <div className="min-w-0 flex-1">
        <h2 className="text-lg">{HEADLINE[e.status]}</h2>
        <p className="max-w-[70ch] text-base">{e.summary}</p>
        {e.status === "sent" && e.sent_at && e.arrives_at && (
          <p className="mt-1 text-sm text-dust-dim">Sent {when(e.sent_at)}, reaches Earth about {when(e.arrives_at)}. Keep following the steps below while you wait.</p>
        )}
        {e.status !== "none" && e.items.length > 0 && (
          <details className="mt-2 text-sm">
            <summary className="cursor-pointer text-dusk">What the message says</summary>
            <ul className="mt-2 list-disc space-y-1 pl-5">{e.items.map((x, i) => <li key={i}>{x}</li>)}</ul>
          </details>
        )}
      </div>
      <Link to={link("/reports")} className="self-center text-sm">Everything sent so far</Link>
    </section>
  );
}
