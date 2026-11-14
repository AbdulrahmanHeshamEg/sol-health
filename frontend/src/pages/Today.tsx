// Today: how you are, what the app needs from you, and what to do.
import { useAssessment, useBrief, useMe, useReminders } from "../api/hooks";
import { DailyBrief } from "../components/DailyBrief";
import { EscalationCard } from "../components/EscalationCard";
import { ActionChecklist, Gauge } from "../components/HealthParts";
import { QuestionsPanel } from "../components/QuestionsPanel";
import { ErrorNote, LEVEL_COLOR, Panel, Skeleton, StatusChip, when } from "../components/ui";

export function Today() {
  const me = useMe();
  if (me.isError) return <ErrorNote error={me.error} retry={() => me.refetch()} />;
  if (!me.data) return <Skeleton lines={8} height={28} />;
  return <TodayFor id={me.data.astronaut_id} />;
}

function TodayFor({ id }: { id: string }) {
  const a = useAssessment(id);
  const brief = useBrief(id);
  const reminders = useReminders(id);
  if (a.isError) return <ErrorNote error={a.error} retry={() => a.refetch()} />;
  if (!a.data) return <Skeleton lines={8} height={28} />;
  const d = a.data;
  const due = reminders.data?.items.filter((i) => i.status === "due") ?? [];

  return (
    <div className="space-y-6">
      <section className="panel grid gap-6 p-6 md:grid-cols-[1fr_auto]" style={{ borderLeft: `6px solid ${LEVEL_COLOR[d.status]}` }}>
        <div>
          <p className="text-base text-dust-dim">{brief.data?.greeting ?? "Hello."} Sol {d.mission_day}, {when(d.timestamp)}.</p>
          <div className="mt-2"><StatusChip level={d.status} large /></div>
          <h1 className="display mt-3 text-2xl">{d.alerts[0]?.message ?? "You are within your own normal today"}</h1>
          <p className="mt-1 max-w-[68ch] text-lg">{d.alerts[0]?.reason ?? "Your heart, sleep, mood, morning tests and the cabin air are all where they usually are for you."}</p>
          {d.alerts.length > 1 && <p className="mt-2 text-sm text-dust-dim">{d.alerts.length - 1} more alert{d.alerts.length > 2 ? "s" : ""} on the My body page.</p>}
        </div>
        <div className="text-center">
          <Gauge score={d.health_score} color={LEVEL_COLOR[d.status]} />
          <p className="text-sm text-dust-dim">your health score</p>
        </div>
      </section>

      <EscalationCard escalation={d.escalation} />

      <Panel title="What to do now" aside={d.actions.length ? "Most urgent first. Ticks are only for you." : undefined}>
        <ActionChecklist actions={d.actions} />
      </Panel>

      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <Panel title="Today's questions">
          <QuestionsPanel astronautId={id} />
        </Panel>
        <div className="space-y-6">
          <DailyBrief astronautId={id} />
          <Panel title="Your routine">
            <ul className="m-0 list-disc space-y-2 pl-5 text-base">{d.daily_plan.map((p, i) => <li key={i}>{p.action}</li>)}</ul>
            {reminders.data && (
              <p className="mt-3 text-sm text-dust-dim">
                {due.length ? `${due.length} measurement${due.length > 1 ? "s" : ""} due now. ` : "No measurement due now. "}
                Check-in streak: <span className="numeral text-base text-dust">{reminders.data.checkin_streak_days}</span> sols.
              </p>
            )}
          </Panel>
        </div>
      </div>
      <p className="max-w-[78ch] text-sm text-dust-dim">{d.disclaimer}</p>
    </div>
  );
}
