// The link to Earth, worked out from the one-way light time the API reports (earth_comm_delay_s):
// distance = light time × c. The same delay sets when reports reach Earth, so the numbers agree everywhere.
import { MarsGlobe } from "./art";

const C_KM_S = 299_792.458;
const AU_KM = 149_597_870.7;

export function lightTime(seconds: number) {
  const s = Math.round(seconds);
  return `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, "0")} s`;
}

export function earthLink(seconds: number) {
  const km = seconds * C_KM_S;
  return { oneWay: lightTime(seconds), roundTrip: lightTime(seconds * 2), millionKm: km / 1e6, au: km / AU_KM };
}

/** Sidebar readout: light time, distance, and a signal dot travelling from Mars to Earth at a pace scaled to the delay. */
export function EarthLink({ seconds }: { seconds: number }) {
  const l = earthLink(seconds);
  // the dot crosses in a second per minute of light time, so a longer delay visibly takes longer
  const crossing = Math.max(4, seconds / 60);
  return (
    <div title={`One-way light time ${l.oneWay}. A reply takes at least ${l.roundTrip}.`}>
      <p className="eyebrow">Signal to Earth</p>
      <p className="mt-1 flex items-baseline gap-1.5">
        <span className="tnum text-lg font-bold leading-none">{l.oneWay}</span>
        <span className="text-xs text-ink-3">one way</span>
      </p>
      <div className="mt-2.5 flex items-center gap-2" aria-hidden="true">
        <MarsGlobe size={14} />
        <span className="relative h-px flex-1" style={{ background: "repeating-linear-gradient(90deg, var(--color-line-strong) 0 4px, transparent 4px 8px)" }}>
          <span className="signal-dot absolute -top-[3px] h-[7px] w-[7px] rounded-full bg-brand" style={{ animationDuration: `${crossing}s` }} />
        </span>
        <span className="h-3.5 w-3.5 rounded-full" style={{ background: "radial-gradient(circle at 35% 35%, #7cc4ff, #1d4ed8 60%, #0b2a6b)" }} />
      </div>
      <p className="tnum mt-2 text-xs text-ink-3">{l.millionKm.toFixed(1)} million km · {l.au.toFixed(2)} AU · reply ≥ {l.roundTrip}</p>
    </div>
  );
}
