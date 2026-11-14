import { AlertOctagon, Atom, Bone } from "lucide-react";
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useForecast, useMeta, useRadiation } from "../api/hooks";
import type { Projection } from "../api/types";
import { AXIS, Legend, TIP } from "./Charts";
import { Card, ErrorNote, LEVEL_COLOR, LEVEL_INK, LEVEL_SOFT, Skeleton, SourceBadge, StatusBadge, fmt } from "./ui";

function LossCard({ title, p, alert, limit }: { title: string; p: Projection; alert?: boolean; limit?: number }) {
  return (
    <div className="rounded-xl border p-4" style={alert ? { borderColor: "var(--color-warn)", background: "var(--color-warn-soft)" } : { borderColor: "var(--color-line)" }}>
      <p className="text-sm font-medium text-ink-2">{title}</p>
      <p className="mt-2 flex flex-wrap items-baseline gap-x-2">
        <span className="tnum text-3xl font-bold" style={{ color: alert ? LEVEL_INK.YELLOW : undefined }}>{fmt(p.projected_loss_pct.median, 1)}%</span>
        <span className="text-sm text-ink-3">projected loss · likely {fmt(p.projected_loss_pct.q10, 1)} to {fmt(p.projected_loss_pct.q90, 1)}%</span>
      </p>
      <p className="mt-2 text-sm text-ink-3">Lost so far: about {fmt(p.estimated_loss_to_date_pct, 1)}%. If the resistive exercise target is met: {fmt(p.projected_loss_if_ared_target_met_pct, 1)}%.</p>
      {alert && limit !== undefined && <p className="mt-2 text-sm font-medium" style={{ color: LEVEL_INK.YELLOW }}>Above the {limit}% planning limit on the current exercise pattern.</p>}
    </div>
  );
}

function Stat({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div className="rounded-xl bg-surface-2 p-3">
      <dt className="text-xs text-ink-3">{label}</dt>
      <dd className="m-0 mt-1"><span className="tnum text-xl font-bold">{value}</span>{unit && <span className="ml-1 text-xs text-ink-3">{unit}</span>}</dd>
    </div>
  );
}

/** Your dose against the career limit, today's dose rate, and the storm banner when a solar storm is under way. */
export function RadiationPanel({ astronautId, showStormBanner = true }: { astronautId: string; showStormBanner?: boolean }) {
  const rad = useRadiation(astronautId);
  const meta = useMeta();
  if (rad.isError) return <ErrorNote error={rad.error} retry={() => rad.refetch()} />;
  if (!rad.data || !meta.data) return <Card><Skeleton lines={5} /></Card>;
  const r = rad.data, lim = meta.data.limits;
  const usedPct = r.career_used_pct, projPct = r.projected_used_pct;
  const scaleMax = Math.max(118, projPct * 1.1);     // leaves room to label the limit
  return (
    <Card title="Radiation" icon={<Atom size={18} />} aside={<SourceBadge source={r.source} />}>
      {showStormBanner && r.spe_in_progress && (
        <div role="alert" className="mb-5 flex items-start gap-3 rounded-xl p-4" style={{ background: LEVEL_SOFT[r.spe_level] }}>
          <AlertOctagon size={20} style={{ color: LEVEL_COLOR[r.spe_level] }} aria-hidden="true" />
          <div>
            <p className="font-semibold" style={{ color: LEVEL_INK[r.spe_level] }}>{r.action}</p>
            <p className="text-sm text-ink-2">{r.reason}</p>
          </div>
        </div>
      )}
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-medium text-ink-2">Career dose against the {fmt(r.career_limit_msv)} mSv limit</p>
            <StatusBadge level={r.budget_status} size="sm" />
          </div>
          <div className="relative mt-9 h-3 rounded-full bg-surface-3">
            <div className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${(projPct / scaleMax) * 100}%`, background: LEVEL_COLOR[r.budget_status], opacity: 0.3 }} />
            <div className="absolute inset-y-0 left-0 rounded-full bg-brand" style={{ width: `${(usedPct / scaleMax) * 100}%` }} />
            {[[lim.dose_yellow_share * 100, "watch"], [100, "limit"]].map(([at, label]) => (
              <div key={label} className="absolute -top-7 -bottom-1 border-l-2 border-dashed border-ink-3 pl-1 text-xs text-ink-3" style={{ left: `${(Number(at) / scaleMax) * 100}%` }}>{label}</div>
            ))}
          </div>
          <p className="mt-3"><span className="tnum text-2xl font-bold">{fmt(usedPct, 1)}%</span> <span className="text-sm text-ink-2">used so far ({fmt(r.career_dose_msv, 1)} mSv, of which {fmt(r.mission_dose_msv, 1)} on this mission)</span></p>
          <p className="mt-1 text-sm text-ink-3">Projected at mission end: {fmt(projPct, 0)}% ({fmt(r.projected_career_at_mission_end_msv)} mSv). The pale bar shows the projection.</p>
        </div>
        <dl className="m-0 grid grid-cols-2 gap-3 self-start">
          <Stat label="Dose rate now" value={fmt(r.dose_rate_ugy_per_day)} unit="µGy/day" />
          <Stat label="vs 7-day normal" value={`${fmt(r.dose_rate_ratio_to_7d, 1)}×`} />
          <Stat label="Last 24 hours" value={fmt(r.dose_last_24h_msv, 2)} unit="mSv" />
          <Stat label="7-day average" value={fmt(r.dose_rate_msv_per_day_7d, 2)} unit="mSv/day" />
        </dl>
      </div>
      <p className="mt-5 max-w-[90ch] text-xs text-ink-3">Absorbed dose is converted to mSv with a quality factor of {r.quality_factor} (Hassler et al. 2014, Mars surface). The dose rate is Curiosity's RAD measurement replayed; it is not a dosimeter worn by a person.</p>
    </Card>
  );
}

export function LongTerm({ astronautId }: { astronautId: string }) {
  const forecast = useForecast(astronautId);
  const meta = useMeta();
  if (forecast.isError) return <ErrorNote error={forecast.error} retry={() => forecast.refetch()} />;
  if (!forecast.data || !meta.data) return <Skeleton lines={8} />;
  const f = forecast.data, lim = meta.data.limits;
  const day0 = f.inputs.mission_day, horizon = f.inputs.horizon_days;
  const months = (d: number) => d / 30;
  const curve = Array.from({ length: 13 }, (_, i) => {
    const d = Math.round(((day0 + horizon) * i) / 12);
    const rate = f.hip_bmd.rate_pct_per_month;
    const target = f.hip_bmd.projected_loss_if_ared_target_met_pct / months(day0 + horizon);
    return { day: d, band: [rate.q10 * months(d), rate.q90 * months(d)], median: rate.median * months(d), target: target * months(d) };
  });

  return (
    <div className="space-y-6">
      <RadiationPanel astronautId={astronautId} />
      <Card title="Bone and muscle" icon={<Bone size={18} />} aside={<SourceBadge source={f.source} />}>
        <div className="grid gap-4 md:grid-cols-2">
          <LossCard title={`Hip bone density by sol ${day0 + horizon}`} p={f.hip_bmd} alert={f.hip_bmd.alert} limit={lim.hip_bmd_loss_alert_pct} />
          <LossCard title={`Thigh muscle by sol ${day0 + horizon}`} p={f.thigh_muscle} />
        </div>
        <figure className="m-0 mt-6">
          <figcaption className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-sm font-semibold">Hip bone density lost, % of pre-flight</span>
            <Legend items={[
              { color: "var(--color-ink-3)", opacity: 0.3, label: "Likely range" },
              { color: "var(--color-ink)", label: "Current pattern", line: true },
              { color: "var(--color-brand)", label: "If exercise target met", line: true },
            ]} />
          </figcaption>
          <ResponsiveContainer width="100%" height={240}>
            <ComposedChart data={curve} margin={{ top: 12, right: 12, bottom: 0, left: -14 }}>
              <CartesianGrid stroke="var(--color-line)" strokeDasharray="3 4" vertical={false} />
              <XAxis dataKey="day" type="number" domain={[0, day0 + horizon]} tickFormatter={(d) => `Sol ${d}`} {...AXIS} />
              <YAxis width={52} {...AXIS} axisLine={false} />
              <Tooltip {...TIP} labelFormatter={(d) => `Sol ${d}`}
                formatter={(v, name) => [Array.isArray(v) ? `${Number(v[0]).toFixed(1)} to ${Number(v[1]).toFixed(1)}%` : `${Number(v).toFixed(1)}%`, name]} />
              <ReferenceLine x={day0} stroke="var(--color-ink-3)" strokeDasharray="4 4" label={{ value: "today", fill: "var(--color-ink-3)", fontSize: 11, position: "insideTopLeft" }} />
              <ReferenceLine y={lim.hip_bmd_loss_alert_pct} stroke="var(--color-warn)" strokeDasharray="5 4" label={{ value: "planning limit", fill: "var(--color-ink-3)", fontSize: 11, position: "insideBottomRight" }} />
              <Area dataKey="band" name="likely range" stroke="none" fill="var(--color-ink-3)" fillOpacity={0.16} isAnimationActive={false} />
              <Line dataKey="median" name="current pattern" stroke="var(--color-ink)" strokeWidth={2} dot={false} isAnimationActive={false} />
              <Line dataKey="target" name="if exercise target met" stroke="var(--color-brand)" strokeWidth={2} strokeDasharray="6 4" dot={false} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </figure>
        <p className="mt-3 max-w-[90ch] text-sm text-ink-3">
          Resistive exercise this week: {fmt(f.inputs.ared_minutes_7d)} of {fmt(lim.ared_target_min_week)} minutes. Aerobic: {fmt(f.inputs.aerobic_minutes_7d)} of {fmt(lim.aerobic_target_min_week)} minutes.
          This projection comes from a model trained on a simulated cohort built from published loss rates.
        </p>
        {f.fitness_trend && (
          <p className="mt-4 rounded-xl bg-surface-2 p-4 text-sm">
            <span className="font-semibold">Fitness trend from exercise heart rate:</span> {f.fitness_trend.reason} <span className="text-ink-3">({f.fitness_trend.sessions} sessions so far.)</span>
          </p>
        )}
      </Card>
    </div>
  );
}
