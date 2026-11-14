// Habitat environment: cabin CO2 against its 1-hour and 7-day limits, and radiation against its 7-day normal.
// Every limit drawn here comes from the API (`/api/meta` limits); the frontend holds no thresholds.
import type { ReactNode } from "react";
import { Atom, CalendarRange, Wind } from "lucide-react";
import { useAssessment, useMeta, useRadiation } from "../api/hooks";
import type { Level } from "../api/types";
import { ErrorNote, LEVEL_COLOR, LEVEL_INK, Skeleton, SourceBadge, fmt } from "./ui";

/** A bar with limit marks; the marks are the API's limits. */
function Meter({ value, max, marks, level }: { value: number | null; max: number; marks: Array<{ at: number; label: string }>; level: Level }) {
  const pct = (x: number) => `${Math.min(100, Math.max(0, (x / max) * 100))}%`;
  return (
    <div className="relative mt-8 h-2 rounded-full bg-surface-3">
      {value !== null && <div className="absolute inset-y-0 left-0 rounded-full" style={{ width: pct(value), background: LEVEL_COLOR[level] }} />}
      {marks.map((m, i) => (
        <div key={m.label} className="absolute -bottom-1 border-l-2 border-dashed border-ink-3 pl-1 text-[0.7rem] leading-4 text-ink-3"
          style={{ left: pct(m.at), top: `${-1.4 - (marks.length - 1 - i) * 1}rem` }}>
          <span className="whitespace-nowrap">{m.label}</span>
        </div>
      ))}
    </div>
  );
}

function Tile({ icon, title, source, value, unit, status, statusText, children, note }: {
  icon: ReactNode; title: string; source?: ReactNode; value: string; unit: string; status: Level; statusText: string; children: ReactNode; note?: string;
}) {
  return (
    <div className="rounded-xl border border-line p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="flex items-center gap-2 text-sm font-medium text-ink-2"><span className="text-ink-3" aria-hidden="true">{icon}</span>{title}</p>
        {source}
      </div>
      <div className="mt-2 flex items-baseline justify-between gap-2">
        <p><span className="tnum text-2xl font-bold">{value}</span> <span className="text-sm text-ink-3">{unit}</span></p>
        <span className="text-sm font-semibold" style={{ color: LEVEL_INK[status] }}>{statusText}</span>
      </div>
      {children}
      {note && <p className="mt-3 text-xs text-ink-3">{note}</p>}
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
  const co2: Level = c.cabin_co2_high ? "YELLOW" : "GREEN";
  const r = rad.data;
  return (
    <div className="grid gap-4 md:grid-cols-3">
      <Tile icon={<Wind size={16} />} title="Cabin CO2, last hour" source={<SourceBadge source={src.cabin_co2_mmhg} />} value={fmt(c.cabin_co2_mmhg, 2)} unit="mmHg"
        status={co2} statusText={c.cabin_co2_high ? "High" : "Nominal"}>
        <Meter value={c.cabin_co2_mmhg} max={lim.cabin_co2_1h_mmhg * 1.6} level={co2} marks={[{ at: lim.cabin_co2_1h_mmhg, label: `limit ${lim.cabin_co2_1h_mmhg}` }]} />
      </Tile>
      <Tile icon={<CalendarRange size={16} />} title="Cabin CO2, 7-day average" value={fmt(c.cabin_co2_7d_mean_mmhg, 2)} unit="mmHg" status={co2} statusText=""
        note={c.cabin_co2_high ? "CO2 is high. A headache or tiredness now is likely the cabin: ventilate first." : "Within both limits."}>
        <Meter value={c.cabin_co2_7d_mean_mmhg} max={lim.cabin_co2_1h_mmhg * 1.6} level={co2} marks={[{ at: lim.cabin_co2_7d_mmhg, label: `limit ${lim.cabin_co2_7d_mmhg}` }]} />
      </Tile>
      <Tile icon={<Atom size={16} />} title="Radiation vs 7-day normal" source={<SourceBadge source={r.source} />} value={`${fmt(r.dose_rate_ratio_to_7d, 1)}×`} unit="normal"
        status={r.spe_level} statusText={r.spe_level === "RED" ? "Shelter" : r.spe_level === "YELLOW" ? "Elevated" : "Nominal"} note={r.reason}>
        <Meter value={r.dose_rate_ratio_to_7d} max={Math.max(lim.radiation_ratio_shelter * 2, r.dose_rate_ratio_to_7d * 1.15)} level={r.spe_level}
          marks={[{ at: lim.radiation_ratio_elevated, label: "elevated" }, { at: lim.radiation_ratio_shelter, label: "shelter" }]} />
      </Tile>
    </div>
  );
}
