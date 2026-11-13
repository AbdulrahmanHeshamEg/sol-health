// Everything that has gone to your flight surgeon on Earth during the mission, newest first.
import { useAssessment, useMe, useReports } from "../api/hooks";
import { EscalationCard } from "../components/EscalationCard";
import { ErrorNote, LEVEL_COLOR, Skeleton, StatusChip, when } from "../components/ui";

export function Reports() {
  const me = useMe();
  const id = me.data?.astronaut_id;
  const reports = useReports(id);
  const now = useAssessment(id ?? "");
  if (me.isError) return <ErrorNote error={me.error} retry={() => me.refetch()} />;
  if (reports.isError) return <ErrorNote error={reports.error} retry={() => reports.refetch()} />;
  if (!me.data || !reports.data) return <Skeleton lines={6} height={30} />;
  const delayMin = Math.round(me.data.flight_surgeon.one_way_delay_s / 60);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl">Your flight surgeon</h1>
        <p className="mt-1 max-w-[72ch] text-base text-dust-dim">
          You are alone on this mission and Earth is about {delayMin} minutes away each way, so you act first. Anything that needs a doctor is
          sent for you: an act-now alert goes at once, a watch alert goes in the daily report at 20:00.
        </p>
      </div>
      {now.data && <EscalationCard escalation={now.data.escalation} />}
      <section>
        <h2 className="text-lg">Sent during the mission</h2>
        {reports.data.length === 0 ? (
          <p className="mt-3 max-w-[60ch] text-base">Nothing has been sent yet. When an alert needs your flight surgeon, it appears here with what was said.</p>
        ) : (
          <ol className="m-0 mt-3 list-none space-y-3 p-0">
            {reports.data.map((r) => (
              <li key={r.started_at} className="panel p-5" style={{ borderLeft: `6px solid ${LEVEL_COLOR[r.level]}` }}>
                <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                  <StatusChip level={r.level} />
                  <h3 className="text-base">{r.condition_label}</h3>
                  <span className="text-sm text-dust-dim">
                    {r.status === "sent" ? `sent at once, ${when(r.sent_at)}` : `in the daily report, ${when(r.sent_at)}`}; reached Earth about {when(r.arrives_at)}
                  </span>
                </div>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-base">{r.items.map((x, i) => <li key={i} className="max-w-[72ch]">{x}</li>)}</ul>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
