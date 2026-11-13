import { Link } from "react-router-dom";
import { useAssessment, useCrew, useMeta, useRadiation } from "../api/hooks";
import type { CrewCard } from "../api/types";
import { useLinkWithAt } from "../state/replay";
import { ErrorNote, LEVEL_COLOR, Panel, Skeleton, SourceBadge, StatusChip, fmt } from "../components/ui";

function CrewRow({ card }: { card: CrewCard }) {
  const link = useLinkWithAt();
  const v = card.vitals;
  return (
    <li>
      <Link to={link(`/crew/${card.astronaut_id}`)}
        className="panel grid gap-x-6 gap-y-3 p-5 text-dust no-underline hover:bg-hab-raised md:grid-cols-[minmax(13rem,1fr)_minmax(0,2.2fr)_auto]"
        style={{ borderLeft: `6px solid ${LEVEL_COLOR[card.status]}` }}>
        <div>
          <StatusChip level={card.status} large />
          <h2 className="mt-2 text-xl">{card.name}</h2>
          <p className="text-sm text-dust-dim">{card.role}</p>
        </div>
        <div className="self-center">
          <p className="display text-lg">{card.top_alert ?? card.condition_label}</p>
          <p className="mt-1 max-w-[62ch] text-base text-dust-dim">
            {card.top_reason ?? "Every indicator is within this person's own normal range."}
          </p>
        </div>
        <dl className="grid grid-cols-5 gap-x-5 self-center text-right md:grid-cols-[repeat(5,auto)]">
          {[
            ["Score", fmt(card.health_score), "/100"],
            ["Heart", fmt(v.heart_rate), "bpm"],
            ["SpO2", fmt(v.spo2), "%"],
            ["Temp", fmt(v.core_temp, 1), "°C"],
            ["BP", `${fmt(v.systolic_bp)}/${fmt(v.diastolic_bp)}`, "mmHg"],
          ].map(([label, value, unit]) => (
            <div key={label}>
              <dt className="text-xs text-dust-dim">{label}</dt>
              <dd className="numeral text-2xl leading-tight">{value}</dd>
              <dd className="text-xs text-dust-dim">{unit}</dd>
            </div>
          ))}
        </dl>
      </Link>
    </li>
  );
}

/** A horizontal scale with limit marks drawn from the API's limits (the frontend holds no thresholds). */
function Scale({ value, max, marks, unit, digits = 2 }: { value: number | null; max: number; marks: Array<{ at: number; label: string }>; unit: string; digits?: number }) {
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

function Habitat({ firstId }: { firstId: string }) {
  const a = useAssessment(firstId);
  const rad = useRadiation(firstId);
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

export function Overview() {
  const crew = useCrew();
  const rad = useRadiation(crew.data?.[0]?.astronaut_id);
  if (crew.isError) return <ErrorNote error={crew.error} retry={() => crew.refetch()} />;
  if (!crew.data) return <Skeleton lines={6} height={40} />;
  const shelter = rad.data?.spe_level === "RED";
  return (
    <div className="space-y-6">
      {shelter && (
        <div role="alert" className="storm-pulse rounded-sm p-4" style={{ background: "var(--color-act)", color: "#2b0f0a" }}>
          <p className="display text-xl">{rad.data!.action}</p>
          <p className="text-base">{rad.data!.reason}</p>
        </div>
      )}
      <h1 className="sr-only">Crew</h1>
      {crew.data.length === 0
        ? <p>No crew in this mission yet. Check that data/demo/crew.json is in place and restart the API.</p>
        : <ul className="m-0 list-none space-y-3 p-0">{crew.data.map((c) => <CrewRow key={c.astronaut_id} card={c} />)}</ul>}
      <Panel title="The habitat" aside="Shared by the whole crew">
        {crew.data[0] && <Habitat firstId={crew.data[0].astronaut_id} />}
      </Panel>
    </div>
  );
}
