import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useForecast, useMeta, useRadiation } from "../api/hooks";
import type { Projection } from "../api/types";
import { ErrorNote, LEVEL_COLOR, Panel, Skeleton, SourceBadge, StatusChip, fmt } from "./ui";

function LossCard({ title, p, alert, limit }: { title: string; p: Projection; alert?: boolean; limit?: number }) {
  return (
    <div>
      <h3 className="text-base">{title}</h3>
      <p className="mt-1"><span className="numeral text-3xl" style={{ color: alert ? LEVEL_COLOR.YELLOW : undefined }}>{fmt(p.projected_loss_pct.median, 1)}%</span>
        <span className="ml-2 text-sm text-dust-dim">projected loss, range {fmt(p.projected_loss_pct.q10, 1)} to {fmt(p.projected_loss_pct.q90, 1)}%</span></p>
      <p className="text-sm text-dust-dim">Lost so far: about {fmt(p.estimated_loss_to_date_pct, 1)}%. If the resistive exercise target is met: {fmt(p.projected_loss_if_ared_target_met_pct, 1)}%.</p>
      {alert && limit !== undefined && <p className="mt-1 text-sm" style={{ color: LEVEL_COLOR.YELLOW }}>Above the {limit}% planning limit on the current exercise pattern.</p>}
    </div>
  );
}


/** Your dose against the career limit, today's dose rate, and the storm banner when a solar storm is under way. */
export function RadiationPanel({ astronautId, showStormBanner = true }: { astronautId: string; showStormBanner?: boolean }) {
  const rad = useRadiation(astronautId);
  const meta = useMeta();
  if (rad.isError) return <ErrorNote error={rad.error} retry={() => rad.refetch()} />;
  if (!rad.data || !meta.data) return <Skeleton lines={5} />;
  const r = rad.data, lim = meta.data.limits;
  const usedPct = r.career_used_pct, projPct = r.projected_used_pct;
  const scaleMax = Math.max(118, projPct * 1.1);     // leaves room to label the limit
  return (
    <Panel title="Radiation" aside={<SourceBadge source={r.source} />}>
      {showStormBanner && r.spe_in_progress && (
        <div role="alert" className="mb-4 rounded-sm p-3" style={{ background: LEVEL_COLOR[r.spe_level], color: "#241505" }}>
          <p className="display text-lg">{r.action}</p>
          <p className="text-sm">{r.reason}</p>
        </div>
      )}
      <div className="grid gap-8 md:grid-cols-[2fr_1fr]">
        <div>
          <h3 className="text-base">Career dose against the {fmt(r.career_limit_msv)} mSv limit</h3>
          <div className="relative mt-8 h-4 rounded-sm bg-basalt">
            <div className="absolute inset-y-0 left-0 rounded-sm" style={{ width: `${(projPct / scaleMax) * 100}%`, background: LEVEL_COLOR[r.budget_status], opacity: 0.35 }} />
            <div className="absolute inset-y-0 left-0 rounded-sm bg-dusk" style={{ width: `${(usedPct / scaleMax) * 100}%` }} />
            {[[lim.dose_yellow_share * 100, "watch"], [100, "limit"]].map(([at, label]) => (
              <div key={label} className="absolute -top-6 bottom-0 border-l border-dashed border-dust-dim pl-1 text-xs text-dust-dim" style={{ left: `${(Number(at) / scaleMax) * 100}%` }}>{label}</div>
            ))}
          </div>
          <p className="mt-2 text-base"><span className="numeral text-2xl">{fmt(usedPct, 1)}%</span> used so far ({fmt(r.career_dose_msv, 1)} mSv, of which {fmt(r.mission_dose_msv, 1)} on this mission).</p>
          <p className="text-sm text-dust-dim">Projected at mission end: {fmt(projPct, 0)}% ({fmt(r.projected_career_at_mission_end_msv)} mSv). The pale bar shows the projection. <StatusChip level={r.budget_status} /></p>
        </div>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 self-start text-sm">
          <div><dt className="text-dust-dim">Dose rate now</dt><dd className="numeral text-xl">{fmt(r.dose_rate_ugy_per_day)} <span className="text-xs text-dust-dim">µGy/day</span></dd></div>
          <div><dt className="text-dust-dim">Compared with the 7-day normal</dt><dd className="numeral text-xl">{fmt(r.dose_rate_ratio_to_7d, 1)}×</dd></div>
          <div><dt className="text-dust-dim">Last 24 hours</dt><dd className="numeral text-xl">{fmt(r.dose_last_24h_msv, 2)} <span className="text-xs text-dust-dim">mSv</span></dd></div>
          <div><dt className="text-dust-dim">7-day average</dt><dd className="numeral text-xl">{fmt(r.dose_rate_msv_per_day_7d, 2)} <span className="text-xs text-dust-dim">mSv/day</span></dd></div>
        </dl>
      </div>
      <p className="mt-3 max-w-[78ch] text-sm text-dust-dim">Absorbed dose is converted to mSv with a quality factor of {r.quality_factor} (Hassler et al. 2014, Mars surface). The dose rate is Curiosity's RAD measurement replayed; it is not a dosimeter worn by a person.</p>
    </Panel>
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

      <Panel title="Bone and muscle" aside={<SourceBadge source={f.source} />}>
        <div className="grid gap-8 md:grid-cols-2">
          <LossCard title={`Hip bone density by sol ${day0 + horizon}`} p={f.hip_bmd} alert={f.hip_bmd.alert} limit={lim.hip_bmd_loss_alert_pct} />
          <LossCard title={`Thigh muscle by sol ${day0 + horizon}`} p={f.thigh_muscle} />
        </div>
        <figure className="m-0 mt-5">
          <figcaption className="text-sm"><span className="display">Hip bone density lost</span> <span className="text-dust-dim">% of pre-flight, current exercise pattern (band) against the exercise target (blue)</span></figcaption>
          <ResponsiveContainer width="100%" height={220}>
            <ComposedChart data={curve} margin={{ top: 8, right: 12, bottom: 0, left: -14 }}>
              <CartesianGrid stroke="var(--color-line)" strokeOpacity={0.35} vertical={false} />
              <XAxis dataKey="day" type="number" domain={[0, day0 + horizon]} tickFormatter={(d) => `sol ${d}`} stroke="var(--color-line)" tick={{ fill: "var(--color-dust-dim)", fontSize: 12 }} />
              <YAxis width={52} stroke="var(--color-line)" tick={{ fill: "var(--color-dust-dim)", fontSize: 12 }} />
              <Tooltip contentStyle={{ background: "var(--color-basalt)", border: "1px solid var(--color-line)", borderRadius: 4 }} labelFormatter={(d) => `Sol ${d}`}
                formatter={(v, name) => [Array.isArray(v) ? `${Number(v[0]).toFixed(1)} to ${Number(v[1]).toFixed(1)}%` : `${Number(v).toFixed(1)}%`, name]} />
              <ReferenceLine x={day0} stroke="var(--color-dust-dim)" strokeDasharray="4 4" label={{ value: "today", fill: "var(--color-dust-dim)", fontSize: 11, position: "insideTopLeft" }} />
              <ReferenceLine y={lim.hip_bmd_loss_alert_pct} stroke="var(--color-dust-dim)" strokeDasharray="5 4" label={{ value: "planning limit", fill: "var(--color-dust-dim)", fontSize: 11, position: "insideBottomRight" }} />
              <Area dataKey="band" name="likely range" stroke="none" fill="var(--color-dust)" fillOpacity={0.16} isAnimationActive={false} />
              <Line dataKey="median" name="current pattern" stroke="var(--color-dust)" strokeWidth={2} dot={false} isAnimationActive={false} />
              <Line dataKey="target" name="if exercise target met" stroke="var(--color-dusk)" strokeWidth={2} strokeDasharray="6 4" dot={false} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </figure>
        <p className="mt-2 max-w-[78ch] text-sm text-dust-dim">
          Resistive exercise this week: {fmt(f.inputs.ared_minutes_7d)} of {fmt(lim.ared_target_min_week)} minutes. Aerobic: {fmt(f.inputs.aerobic_minutes_7d)} of {fmt(lim.aerobic_target_min_week)} minutes.
          This projection comes from a model trained on a simulated cohort built from published loss rates.
        </p>
        {f.fitness_trend && (
          <p className="mt-3 max-w-[78ch] text-base">
            <span className="font-bold">Fitness trend from exercise heart rate:</span> {f.fitness_trend.reason} <span className="text-sm text-dust-dim">({f.fitness_trend.sessions} sessions so far.)</span>
          </p>
        )}
      </Panel>
    </div>
  );
}
