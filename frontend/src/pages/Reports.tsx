// Your flight surgeon: the next appointment (tonight's report, or an urgent message) and everything sent so far.
import { CalendarClock, History, Satellite } from "lucide-react";
import { useAssessment, useMe, useReports } from "../api/hooks";
import type { Assessment } from "../api/types";
import { Card, ErrorNote, LEVEL_COLOR, PageHeader, Skeleton, StatusBadge, clock, when } from "../components/ui";
import { parseTs } from "../state/replay";
import { earthLink } from "../components/EarthLink";

function NextAppointment({ a }: { a: Assessment }) {
  const e = a.escalation;
  const agenda = a.actions.filter((x) => x.who === "ground");
  if (e.status === "none" || !e.sent_at) {
    return (
      <Card title="Next appointment" icon={<CalendarClock size={18} />}>
        <p className="text-sm text-ink-2">Nothing to send today. Your daily report goes out at 20:00 only when something needs your flight surgeon.</p>
      </Card>
    );
  }
  const sent = parseTs(e.sent_at).getTime() <= parseTs(a.timestamp).getTime();
  return (
    <section className="card overflow-hidden">
      <div className="flex flex-wrap items-center gap-4 p-5" style={{ background: "var(--color-brand-soft)" }}>
        <div className="grid h-16 w-16 shrink-0 place-items-center rounded-2xl bg-surface text-center shadow-[var(--shadow-card)]">
          <span className="tnum text-lg font-bold leading-none text-brand-ink">{clock(e.sent_at)}</span>
          <span className="text-[0.65rem] text-ink-3">UTC</span>
        </div>
        <div className="min-w-0 flex-1">
          <p className="eyebrow" style={{ color: "var(--color-brand-ink)" }}>{sent ? "Sent" : "Next appointment"}</p>
          <h2 className="text-lg font-semibold">{e.status === "sent" ? "Urgent message to your flight surgeon" : "Daily report to your flight surgeon"}</h2>
          <p className="mt-0.5 text-sm text-ink-2">Reaches Earth at {e.arrives_at ? clock(e.arrives_at) : "about 13 minutes later"}. {e.status === "sent" ? "Keep working through your plan while you wait for the reply." : "You don't need to do anything for it."}</p>
        </div>
        <StatusBadge level={e.level} />
      </div>
      <div className="grid gap-6 p-5 md:grid-cols-2">
        <div>
          <p className="eyebrow">On the agenda</p>
          {agenda.length === 0 ? <p className="mt-2 text-sm text-ink-2">Nothing for your flight surgeon to act on.</p> : (
            <ul className="m-0 mt-2 list-disc space-y-1.5 pl-5 text-sm">{agenda.map((x) => <li key={x.priority}>{x.action}</li>)}</ul>
          )}
        </div>
        <div>
          <p className="eyebrow">What the message says</p>
          <ul className="m-0 mt-2 list-disc space-y-1.5 pl-5 text-sm text-ink-2">{e.items.map((x, i) => <li key={i}>{x}</li>)}</ul>
        </div>
      </div>
    </section>
  );
}

export function Reports() {
  const me = useMe();
  const id = me.data?.astronaut_id;
  const reports = useReports(id);
  const now = useAssessment(id ?? "");
  if (me.isError) return <ErrorNote error={me.error} retry={() => me.refetch()} />;
  if (reports.isError) return <ErrorNote error={reports.error} retry={() => reports.refetch()} />;
  if (!me.data || !reports.data) return <Skeleton lines={6} height={30} />;
  const link = earthLink(me.data.flight_surgeon.one_way_delay_s);

  return (
    <div className="space-y-6">
      <PageHeader title="Flight surgeon"
        subtitle={`A message takes ${link.oneWay} to reach Earth (${link.millionKm.toFixed(1)} million km) and a reply at least ${link.roundTrip}, so you act first and your flight surgeon follows up. An act-now alert is sent at once. A watch alert goes in the daily report at 20:00.`} />
      {now.data && <NextAppointment a={now.data} />}
      <Card title="Sent during the mission" icon={<History size={18} />} aside={`${reports.data.length} message${reports.data.length === 1 ? "" : "s"}`}>
        {reports.data.length === 0 ? (
          <p className="flex items-center gap-2 text-sm text-ink-2"><Satellite size={16} className="text-ink-3" aria-hidden="true" />Nothing sent yet.</p>
        ) : (
          <ol className="relative m-0 list-none space-y-4 border-l-2 border-line p-0 pl-6">
            {reports.data.map((r) => (
              <li key={r.started_at} className="relative">
                <span className="absolute -left-[31px] top-1.5 h-3.5 w-3.5 rounded-full border-2 border-surface" style={{ background: LEVEL_COLOR[r.level] }} aria-hidden="true" />
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <StatusBadge level={r.level} size="sm" />
                  <h3 className="font-semibold">{r.condition_label}</h3>
                </div>
                <p className="mt-1 text-xs text-ink-3">
                  {r.status === "sent" ? `Sent at once, ${when(r.sent_at)}` : `Daily report, ${when(r.sent_at)}`}. Reached Earth about {clock(r.arrives_at)}.
                </p>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink-2">{r.items.map((x, i) => <li key={i}>{x}</li>)}</ul>
              </li>
            ))}
          </ol>
        )}
      </Card>
    </div>
  );
}
