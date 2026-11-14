// My body: every system and indicator against your own normal, the trends, and the long-term view.
import { useSearchParams } from "react-router-dom";
import { PersonStanding, Scale } from "lucide-react";
import { useAssessment, useDaily, useIndicators, useMe, useMeta, useTimeline, useVitals } from "../api/hooks";
import { BodyFigure } from "../components/BodyFigure";
import { DailyCharts, HourlyCharts } from "../components/Charts";
import { DAILY, Evidence, hourlySeries } from "../components/HealthParts";
import { CategoryLabel, HighlightCard, MetricCard } from "../components/Metric";
import { CATEGORY, METRICS, type CatId } from "../lib/health";
import { LongTerm } from "../components/LongTerm";
import { Eyes } from "./Eyes";
import { Card, ErrorNote, PageHeader, Skeleton, Tabs, signed } from "../components/ui";

const TABS = [["now", "Now"], ["trends", "Trends"], ["long", "Long-term"], ["eyes", "Eye exam"]] as const;
type Tab = (typeof TABS)[number][0];
const GROUPS: CatId[] = ["heart", "respiratory", "body", "sleep", "mind", "labs"];

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
      <PageHeader title="My body" subtitle="Each reading next to your own normal, how it has moved lately, and where it is heading." />
      <Tabs tabs={TABS} value={tab} onChange={setTab} label="View" />

      {tab === "now" && (
        <div className="space-y-8">
          {d.alerts.length > 0 && (
            <section aria-labelledby="body-hl">
              <h2 id="body-hl" className="section-title px-1">Highlights</h2>
              <div className="mt-2 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {d.alerts.map((x, i) => <HighlightCard key={i} alert={x} hourly={vitals.data} daily={daily.data} stamp="Today" />)}
              </div>
              {d.drivers.length > 0 && (
                <p className="mt-3 px-1 text-xs text-ink-3">
                  Furthest from your normal today: {d.drivers.map((x) => `${x.signal.replace(/_/g, " ")} (${signed(x.z)} SD)`).join(", ")}. Positive means worse.
                </p>
              )}
            </section>
          )}
          {GROUPS.map((cat) => {
            const list = METRICS.filter((m) => m.cat === cat);
            return (
              <section key={cat} aria-label={CATEGORY[cat].label}>
                <div className="px-1"><CategoryLabel cat={cat} /></div>
                <div className="mt-2 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {list.map((m) => <MetricCard key={m.key} m={m} a={d} hourly={vitals.data} daily={daily.data} />)}
                </div>
              </section>
            );
          })}
          <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
            <Card title="Body systems" icon={<PersonStanding size={18} />}><BodyFigure systems={d.body_systems} cards={cards.data} /></Card>
            <Card title="How the evidence splits" icon={<Scale size={18} />} aside="Relative weight per condition, not a probability"><Evidence a={d} /></Card>
          </div>
        </div>
      )}

      {tab === "trends" && (
        <div className="space-y-6">
          <Card title="Last 72 hours">
            {vitals.isError ? <ErrorNote error={vitals.error} retry={() => vitals.refetch()} />
              : vitals.data && timeline.data ? <HourlyCharts rows={vitals.data} timeline={timeline.data} series={hourlySeries(meta.data?.limits.cabin_co2_1h_mmhg)} />
              : <Skeleton lines={5} height={24} />}
          </Card>
          <Card title="Last 30 sols">
            {daily.isError ? <ErrorNote error={daily.error} retry={() => daily.refetch()} />
              : !daily.data ? <Skeleton lines={5} height={24} />
              : daily.data.length === 0 ? <p className="text-sm text-ink-2">No daily entries yet. They start after your first night.</p>
              : <DailyCharts rows={daily.data} series={DAILY} />}
          </Card>
        </div>
      )}

      {tab === "long" && <LongTerm astronautId={id} />}

      {tab === "eyes" && <Eyes embedded />}
    </div>
  );
}
