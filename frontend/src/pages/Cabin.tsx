// Cabin view: the habitat you live in, not your body. CO2 and radiation now, over the last 72 hours, and your dose budget.
import { useMe, useMeta, useRadiation, useTimeline, useVitals } from "../api/hooks";
import { HourlyCharts, type Series } from "../components/Charts";
import { Habitat } from "../components/Habitat";
import { RadiationPanel } from "../components/LongTerm";
import { ErrorNote, Panel, Skeleton } from "../components/ui";

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
    { key: "cabin_co2_mmhg", label: "Cabin CO2", unit: "mmHg", limit: meta.data?.limits.cabin_co2_1h_mmhg, limitLabel: "1-hour limit" },
    { key: "radiation_ugy_per_day", label: "Radiation dose rate", unit: "µGy/day" },
  ];
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl">Cabin</h1>
        <p className="mt-1 max-w-[70ch] text-base text-dust-dim">
          The air you breathe and the radiation reaching the habitat. When CO2 is high, a headache or tiredness is probably the cabin, not you: ventilate first.
        </p>
      </div>
      {rad.data?.spe_level === "RED" && (
        <div role="alert" className="storm-pulse rounded-sm p-4" style={{ background: "var(--color-act)", color: "#2b0f0a" }}>
          <p className="display text-xl">{rad.data.action}</p>
          <p className="text-base">{rad.data.reason}</p>
        </div>
      )}
      <Panel title="Right now"><Habitat id={id} /></Panel>
      <Panel title="Last 72 hours">
        {vitals.isError ? <ErrorNote error={vitals.error} retry={() => vitals.refetch()} />
          : vitals.data && timeline.data ? <HourlyCharts rows={vitals.data} timeline={timeline.data} series={series} /> : <Skeleton lines={4} height={24} />}
      </Panel>
      <RadiationPanel astronautId={id} showStormBanner={false} />
    </div>
  );
}
