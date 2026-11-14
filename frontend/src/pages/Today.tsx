// Today: the summary you open every morning. Highlights (what is off) and your pinned readings on the left,
// your plan for the day on the right. The date is always today's; the simulated day only sets the data.
import { Link } from "react-router-dom";
import { ClipboardCheck } from "lucide-react";
import { useAssessment, useDaily, useMe, useReminders, useVitals } from "../api/hooks";
import type { Assessment } from "../api/types";
import { useCheckInSteps } from "../components/CheckInWizard";
import { HighlightCard, MetricCard } from "../components/Metric";
import { Planner } from "../components/Planner";
import { AllClearArt } from "../components/art";
import { ErrorNote, ScoreRing, Skeleton, StatusBadge } from "../components/ui";
import { isEyeAlert } from "../lib/eye";
import { metric } from "../lib/health";
import { useCheckIn } from "../state/checkin";
import { displayDate, useLinkWithAt } from "../state/replay";

const PINNED = ["heart_rate", "spo2", "sleep_hours", "mood", "core_temp", "systolic_bp"];

export function Today() {
  const me = useMe();
  if (me.isError) return <ErrorNote error={me.error} retry={() => me.refetch()} />;
  if (!me.data) return <Skeleton lines={8} height={28} />;
  return <TodayFor id={me.data.astronaut_id} name={me.data.name} />;
}

function Overall({ d }: { d: Assessment }) {
  const link = useLinkWithAt();
  const shown = d.alerts.filter((x) => !isEyeAlert(x)).length;
  return (
    <div className="card flex items-center gap-4 p-4">
      <ScoreRing score={d.health_score} level={d.status} size={64} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2"><p className="font-semibold">Health score</p><StatusBadge level={d.status} size="sm" /></div>
        <p className="mt-0.5 text-sm text-ink-3">
          {shown ? `${shown} thing${shown > 1 ? "s" : ""} to keep an eye on today.` : d.status === "GREEN" ? "Everything is within your own normal." : "Your monthly eye check has something to look at."}
          {!shown && d.status !== "GREEN" && <> <Link to={link("/body?tab=eyes")}>Open it</Link></>}
        </p>
      </div>
    </div>
  );
}

function CheckInCard({ id }: { id: string }) {
  const { show } = useCheckIn();
  const { query, steps, answered, total } = useCheckInSteps(id);
  const done = total > 0 && answered === total;
  return (
    <section className="card flex items-center gap-3 p-4">
      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand text-white"><ClipboardCheck size={20} aria-hidden="true" /></span>
      <div className="min-w-0 flex-1">
        <p className="font-semibold">Daily check-in</p>
        <p className="text-xs text-ink-3">{!query.data ? "Loading" : done ? "Done. You can still change your answers." : `${steps.length} short steps, about a minute`}</p>
      </div>
      <button className="btn-ghost" onClick={show} disabled={!query.data}>{done ? "Edit" : answered ? "Continue" : "Start"}</button>
    </section>
  );
}

const partOfDay = (ts: string) => { const h = Number(ts.slice(11, 13)); return h < 12 ? "morning" : h < 18 ? "afternoon" : "evening"; };

function TodayFor({ id, name }: { id: string; name: string }) {
  const a = useAssessment(id);
  const vitals = useVitals(id);
  const daily = useDaily(id);
  const reminders = useReminders(id);
  const { show } = useCheckIn();
  const link = useLinkWithAt();
  if (a.isError) return <ErrorNote error={a.error} retry={() => a.refetch()} />;
  if (!a.data) return <div className="space-y-6"><Skeleton lines={2} height={30} /><Skeleton lines={6} height={40} /></div>;
  const d = a.data;
  const highlights = d.alerts.filter((x) => !isEyeAlert(x));
  const day = displayDate(d.timestamp).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" });

  return (
    <div className="space-y-6">
      <div>
        <p className="text-[0.8rem] font-semibold uppercase tracking-wide text-ink-3">{day} · Sol {d.mission_day}</p>
        <h1 className="mt-0.5 text-[2.125rem] font-bold leading-tight tracking-tight">Summary</h1>
        <p className="text-sm text-ink-3">Good {partOfDay(d.timestamp)}, {name.split(" ")[0]}.</p>
      </div>

      <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1.35fr)_minmax(320px,1fr)]">
        <div className="space-y-8">
          <section aria-labelledby="hl">
            <h2 id="hl" className="section-title px-1">Highlights</h2>
            <div className="mt-2 space-y-3">
              <Overall d={d} />
              {highlights.length === 0 ? (
                <div className="card flex items-center gap-4 p-4">
                  <AllClearArt size={56} />
                  <p className="text-sm text-ink-2">No highlights today. Your readings are where they usually are for you.</p>
                </div>
              ) : (
                <div className={`grid gap-3 ${highlights.length > 1 ? "md:grid-cols-2" : ""}`}>
                  {highlights.map((x, i) => <HighlightCard key={i} alert={x} hourly={vitals.data} daily={daily.data} stamp="Today" />)}
                </div>
              )}
            </div>
          </section>

          <section aria-labelledby="pinned">
            <div className="flex items-end justify-between px-1">
              <h2 id="pinned" className="section-title">Pinned</h2>
              <Link to={link("/body")} className="text-[0.95rem] no-underline">Show all</Link>
            </div>
            <div className="mt-2 grid gap-3 md:grid-cols-2">
              {PINNED.map((k) => metric(k)).map((m) => m && <MetricCard key={m.key} m={m} a={d} hourly={vitals.data} daily={daily.data} to="/body" />)}
            </div>
          </section>
        </div>

        <div className="space-y-4">
          <CheckInCard id={id} />
          <Planner a={d} reminders={reminders.data} onCheckIn={show} />
        </div>
      </div>
      <p className="max-w-[90ch] text-xs text-ink-3">{d.disclaimer}</p>
    </div>
  );
}
