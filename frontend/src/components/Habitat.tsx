// Habitat environment: cabin CO2 against its 1-hour and 7-day limits, and radiation against its 7-day normal.
// Every limit drawn here comes from the API (`/api/meta` limits); the frontend holds no thresholds.
import { useAssessment, useMeta, useRadiation } from "../api/hooks";
import { ErrorNote, Skeleton, SourceBadge, fmt } from "./ui";

/** A horizontal scale with limit marks drawn from the API's limits (the frontend holds no thresholds). */
export function Scale({ value, max, marks, unit, digits = 2 }: { value: number | null; max: number; marks: Array<{ at: number; label: string }>; unit: string; digits?: number }) {
  const pct = (x: number) => `${Math.min(100, Math.max(0, (x / max) * 100))}%`;
  return (
    <div>
      <div className="relative h-3 rounded-sm bg-basalt" style={{ marginTop: marks.length > 1 ? "3rem" : "1.75rem" }}>
        {value !== null && <div className="absolute inset-y-0 left-0 rounded-sm bg-dusk" style={{ width: pct(value) }} />}
        {marks.map((m, i) => (
          // labels step upward so neighbouring marks never overlap on a narrow screen
          <div key={m.label} className="absolute bottom-0 border-l border-dashed border-dust-dim pl-1 text-xs leading-4 text-dust-dim"
            style={{ left: pct(m.at), top: `${-1.5 - (marks.length - 1 - i) * 1.1}rem` }}>
            <span className="whitespace-nowrap">{m.label}</span>
          </div>
        ))}
      </div>
      <p className="mt-1 text-sm"><span className="numeral text-xl">{fmt(value, digits)}</span> <span className="text-dust-dim">{unit}</span></p>
    </div>
  );
}

export function Habitat({ id }: { id: string }) {
  const a = useAssessment(id);
  const rad = useRadiation(id);
  const meta = useMeta();
  const lim = meta.data?.limits;
  if (a.isError) return <ErrorNote error={a.error} retry={() => a.refetch()} />;
  if (!a.data || !rad.data || !lim) return <Skeleton lines={4} />;
  const c = a.data.context;
  const src = meta.data!.sources;
  return (
    <div className="grid gap-8 md:grid-cols-3">
      <div>
        <h3 className="text-base">Cabin CO2, last hour <SourceBadge source={src.cabin_co2_mmhg} /></h3>
        <Scale value={c.cabin_co2_mmhg} max={lim.cabin_co2_1h_mmhg * 2} unit="mmHg" marks={[{ at: lim.cabin_co2_1h_mmhg, label: `limit ${lim.cabin_co2_1h_mmhg}` }]} />
      </div>
      <div>
        <h3 className="text-base">Cabin CO2, 7-day average</h3>
        <Scale value={c.cabin_co2_7d_mean_mmhg} max={lim.cabin_co2_1h_mmhg * 2} unit="mmHg" marks={[{ at: lim.cabin_co2_7d_mmhg, label: `limit ${lim.cabin_co2_7d_mmhg}` }]} />
        <p className="text-sm text-dust-dim">{c.cabin_co2_high ? "CO2 is high. A headache or fatigue now is likely environmental: ventilate first." : "Within both limits."}</p>
      </div>
      <div>
        <h3 className="text-base">Radiation vs the 7-day normal <SourceBadge source={rad.data.source} /></h3>
        <Scale value={rad.data.dose_rate_ratio_to_7d} max={Math.max(lim.radiation_ratio_shelter * 2, rad.data.dose_rate_ratio_to_7d * 1.15)} unit="times normal" digits={1}
          marks={[{ at: lim.radiation_ratio_elevated, label: "elevated" }, { at: lim.radiation_ratio_shelter, label: "shelter" }]} />
        <p className="text-sm text-dust-dim">{rad.data.reason}</p>
      </div>
    </div>
  );
}

