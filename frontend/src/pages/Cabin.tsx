// Cabin view: the habitat you live in, not your body. CO2 and radiation now, over the last 72 hours, and your dose budget.
import { AlertOctagon, Gauge, LineChart } from "lucide-react";
import { useMe, useMeta, useRadiation, useTimeline, useVitals } from "../api/hooks";
import { HourlyCharts, type Series } from "../components/Charts";
import { Habitat } from "../components/Habitat";
import { RadiationPanel } from "../components/LongTerm";
import { Card, ErrorNote, PageHeader, Skeleton } from "../components/ui";

export function Cabin() {
  const me = useMe();
  const id = me.data?.astronaut_id ?? "";
  const vitals = useVitals(id);
  const timeline = useTimeline(id);
  const rad = useRadiation(me.data?.astronaut_id);
  const meta = useMeta();
  if (me.isError) return <ErrorNote error={me.error} retry={() => me.refetch()} />;
  if (!me.data) return <Skeleton lines={6} height={30} />;
  const series: Series[] = [
    { key: "cabin_co2_mmhg", label: "Cabin CO2", unit: "mmHg", limit: meta.data?.limits.cabin_co2_1h_mmhg, limitLabel: "1-hour limit", digits: 2 },
    { key: "radiation_ugy_per_day", label: "Radiation dose rate", unit: "µGy/day", digits: 0 },
  ];
  return (
    <div className="space-y-6">
      <PageHeader title="Cabin" subtitle="The air you breathe and the radiation reaching the habitat. When CO2 is high, a headache or tiredness is probably the cabin, not you: ventilate first." />
      {rad.data?.spe_level === "RED" && (
        <div role="alert" className="flex items-start gap-4 rounded-2xl p-5 text-white" style={{ background: "linear-gradient(135deg, #dc2626, #9f1239)" }}>
          <span className="storm-pulse grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-white/15"><AlertOctagon size={24} /></span>
          <div><p className="text-lg font-bold">{rad.data.action}</p><p className="mt-0.5 text-white/90">{rad.data.reason}</p></div>
        </div>
      )}
      <Card title="Right now" icon={<Gauge size={18} />}><Habitat id={id} /></Card>
      <Card title="Last 72 hours" icon={<LineChart size={18} />}>
        {vitals.isError ? <ErrorNote error={vitals.error} retry={() => vitals.refetch()} />
          : vitals.data && timeline.data ? <HourlyCharts rows={vitals.data} timeline={timeline.data} series={series} /> : <Skeleton lines={4} height={24} />}
      </Card>
      <RadiationPanel astronautId={id} showStormBanner={false} />
    </div>
  );
}
