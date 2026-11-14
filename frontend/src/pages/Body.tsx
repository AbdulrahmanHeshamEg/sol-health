// My body: every system and indicator against your own normal, the trends, and the long-term view.
import { useSearchParams } from "react-router-dom";
import { useAssessment, useDaily, useIndicators, useMe, useMeta, useTimeline, useVitals } from "../api/hooks";
import { BodyFigure } from "../components/BodyFigure";
import { DailyCharts, HourlyCharts } from "../components/Charts";
import { AlertItem, DAILY, Evidence, Readings, hourlySeries } from "../components/HealthParts";
import { LongTerm } from "../components/LongTerm";
import { ErrorNote, Panel, Skeleton, signed } from "../components/ui";

const TABS = [["now", "Now"], ["trends", "Trends"], ["long", "Long-term"]] as const;
type Tab = (typeof TABS)[number][0];

export function Body() {
  const me = useMe();
  if (me.isError) return <ErrorNote error={me.error} retry={() => me.refetch()} />;
  if (!me.data) return <Skeleton lines={8} height={28} />;
  return <BodyFor id={me.data.astronaut_id} />;
}

function BodyFor({ id }: { id: string }) {
  const [params, setParams] = useSearchParams();
  const tab = (TABS.find(([k]) => k === params.get("tab"))?.[0] ?? "now") as Tab;
  const setTab = (next: Tab) => setParams((prev) => {
    const p = new URLSearchParams(prev);
    if (next === "now") p.delete("tab"); else p.set("tab", next);
    return p;
  }, { replace: true });
  const a = useAssessment(id);
  const cards = useIndicators();
  const vitals = useVitals(id);
  const timeline = useTimeline(id);
  const daily = useDaily(id);
  const meta = useMeta();
  if (a.isError) return <ErrorNote error={a.error} retry={() => a.refetch()} />;
  if (!a.data) return <Skeleton lines={8} height={28} />;
  const d = a.data;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-2xl">My body</h1>
        <div className="flex gap-2" role="tablist" aria-label="View">
          {TABS.map(([k, label]) => (
            <button key={k} role="tab" aria-selected={tab === k} aria-pressed={tab === k} className="btn-quiet" onClick={() => setTab(k)}>{label}</button>
          ))}
        </div>
      </div>

      {tab === "now" && (
        <>
          <div className="grid gap-6 lg:grid-cols-2">
            <Panel title="Your body systems"><BodyFigure systems={d.body_systems} cards={cards.data} /></Panel>
            <Panel title={d.alerts.length ? `Why: ${d.alerts.length} alert${d.alerts.length > 1 ? "s" : ""}` : "Why"}>
              {d.alerts.length === 0
                ? <p className="text-base">No alerts. Your clinical limits, your own baselines, the cabin air and radiation are checked every hour.</p>
                : <ul className="m-0 list-none space-y-4 p-0">{d.alerts.map((x, i) => <AlertItem key={i} alert={x} />)}</ul>}
              {d.drivers.length > 0 && (
                <p className="mt-5 text-sm text-dust-dim">
                  Furthest from your normal today: {d.drivers.map((x) => `${x.signal.replace("_", " ")} (${signed(x.z)} SD)`).join(", ")}. Positive means worse.
                </p>
              )}
            </Panel>
          </div>
          <Panel title="Every indicator against your own normal"><Readings a={d} /></Panel>
          <Panel title="How the evidence splits" aside="Relative weight per condition, not a probability"><Evidence a={d} /></Panel>
        </>
      )}

      {tab === "trends" && (
        <>
          <Panel title="Last 72 hours">
            {vitals.isError ? <ErrorNote error={vitals.error} retry={() => vitals.refetch()} />
              : vitals.data && timeline.data ? <HourlyCharts rows={vitals.data} timeline={timeline.data} series={hourlySeries(meta.data?.limits.cabin_co2_1h_mmhg)} />
              : <Skeleton lines={5} height={24} />}
          </Panel>
          <Panel title="Last 30 sols">
            {daily.isError ? <ErrorNote error={daily.error} retry={() => daily.refetch()} />
              : !daily.data ? <Skeleton lines={5} height={24} />
              : daily.data.length === 0 ? <p>No daily entries yet. They start after your first night.</p>
              : <DailyCharts rows={daily.data} series={DAILY} />}
          </Panel>
        </>
      )}

      {tab === "long" && <LongTerm astronautId={id} />}
    </div>
  );
}
