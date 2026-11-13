import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAssessment, useDaily, useIndicators, useMe, useMeta, useReminders, useTimeline, useVitals } from "../api/hooks";
import type { Action, Alert, Assessment, Who } from "../api/types";
import { BodyFigure } from "../components/BodyFigure";
import { DailyCharts, HourlyCharts, type DailySeries, type Series } from "../components/Charts";
import { CheckIn } from "../components/CheckIn";
import { EscalationCard } from "../components/EscalationCard";
import { LongTerm } from "../components/LongTerm";
import { ErrorNote, LEVEL_COLOR, Panel, Skeleton, SourceBadge, StatusChip, StatusIcon, WHO_LABEL, fmt, signed, when } from "../components/ui";

const VITAL_LABEL: Record<string, string> = {
  heart_rate: "Heart rate", hrv_rmssd: "Heart rate variability", spo2: "Blood oxygen", resp_rate: "Breathing rate",
  systolic_bp: "Blood pressure, upper", diastolic_bp: "Blood pressure, lower", core_temp: "Body temperature", pvt_reaction_ms: "Reaction time",
};
const DAILY: DailySeries[] = [
  { key: "resting_hr", label: "Resting heart rate", unit: "bpm" },
  { key: "sleep_hours", label: "Sleep", unit: "hours" },
  { key: "mood", label: "Mood", unit: "score, 5 = best", domain: [1, 5] },
  { key: "stress", label: "Stress", unit: "score, 5 = relaxed", domain: [1, 5] },
  { key: "fatigue", label: "Energy", unit: "score, 5 = fresh", domain: [1, 5] },
  { key: "blood_glucose_mg_dl", label: "Fasting blood sugar", unit: "mg/dL" },
];

function Gauge({ score, color }: { score: number; color: string }) {
  const r = 46, c = Math.PI * r;
  return (
    <svg width="124" height="74" viewBox="0 0 124 74" className="mx-auto block" role="img" aria-label={`Health score ${score} out of 100`}>
      <path d="M16 66a46 46 0 0192 0" fill="none" stroke="var(--color-basalt)" strokeWidth="11" strokeLinecap="round" />
      <path d="M16 66a46 46 0 0192 0" fill="none" stroke={color} strokeWidth="11" strokeLinecap="round" strokeDasharray={`${(score / 100) * c} ${c}`} />
      <text x="62" y="62" textAnchor="middle" className="numeral" fontSize="30" fill="var(--color-dust)">{score}</text>
    </svg>
  );
}

function ActionChecklist({ actions }: { actions: Action[] }) {
  const [done, setDone] = useState<Record<string, boolean>>({});
  if (actions.length === 0) return <p className="text-base">Nothing needs doing right now. The daily plan below keeps it that way.</p>;
  const groups = (["self", "ground"] as Who[]).map((who) => [who, actions.filter((a) => a.who === who)] as const).filter(([, list]) => list.length);
  return (
    <div className="grid gap-x-8 gap-y-5 md:grid-cols-2">
      {groups.map(([who, list]) => (
        <div key={who}>
          <h3 className="text-base text-dust-dim">{WHO_LABEL[who]}</h3>
          <ul className="m-0 mt-2 list-none space-y-2 p-0">
            {list.map((a) => {
              const id = `${a.who}-${a.priority}`;
              return (
                <li key={id}>
                  <label className="flex cursor-pointer items-start gap-3 text-base">
                    <input type="checkbox" checked={!!done[id]} onChange={(e) => setDone({ ...done, [id]: e.target.checked })}
                      className="mt-1 h-5 w-5 shrink-0" style={{ accentColor: LEVEL_COLOR[a.level] }} />
                    <span style={{ textDecoration: done[id] ? "line-through" : "none", opacity: done[id] ? 0.6 : 1 }}>
                      <span className="mr-2 inline-block align-[-3px]"><StatusIcon level={a.level} size={16} /></span>{a.action}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}

function AlertItem({ alert }: { alert: Alert }) {
  return (
    <li className="border-l-4 pl-4" style={{ borderColor: LEVEL_COLOR[alert.level] }}>
      <p className="display text-base">{alert.message}</p>
      <p className="max-w-[70ch] text-base">{alert.reason}</p>
      <p className="mt-1 text-sm text-dust-dim">
        {alert.source === "rule" ? "Clinical limit" : `Statistical model: ${alert.model ?? "body model"}`}
        {alert.threshold ? `, fires at ${alert.threshold}` : ""}. Hazard: {alert.hazard.toLowerCase()}.
      </p>
    </li>
  );
}

function Readings({ a }: { a: Assessment }) {
  const flagged = new Set(a.alerts.map((x) => x.signal));
  const cells = [
    ...Object.entries(a.indicators).map(([key, r]) => ({ key, label: r.label, value: r.value, unit: r.unit, baseline: r.baseline, delta: r.delta, source: r.source,
      digits: key === "sleep_hours" ? 1 : 0, hit: flagged.has(key === "sleep_hours" ? "sleep_minutes" : key) })),
    ...Object.entries(a.vitals).map(([key, r]) => ({ key, label: VITAL_LABEL[key] ?? key, value: r.value, unit: r.unit, baseline: r.baseline, delta: r.delta, source: r.source,
      digits: key === "core_temp" ? 1 : 0, hit: flagged.has(key) })),
  ];
  return (
    <dl className="grid pl-px pt-px sm:grid-cols-2 lg:grid-cols-4">
      {cells.map((c) => (
        <div key={c.key} className="-ml-px -mt-px border border-line p-4" style={c.hit ? { boxShadow: `inset 4px 0 0 ${LEVEL_COLOR.YELLOW}` } : undefined}>
          <dt className="flex items-start justify-between gap-2 text-sm text-dust-dim"><span>{c.label}</span><SourceBadge source={c.source} /></dt>
          <dd className="mt-1"><span className="numeral text-3xl">{fmt(c.value, c.digits)}</span> <span className="text-sm text-dust-dim">{c.unit}</span></dd>
          <dd className="text-sm text-dust-dim">
            {c.baseline === null ? "No baseline yet" : `Your normal ${fmt(c.baseline, c.digits)}, ${c.delta === 0 ? "no change" : signed(c.delta, c.digits === 0 ? 0 : 1)}`}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function Evidence({ a }: { a: Assessment }) {
  const meta = useMeta();
  const labels = Object.fromEntries((meta.data?.conditions ?? []).map((c) => [c.id, c.label]));
  const rows = Object.entries(a.probabilities).filter(([, p]) => p > 0.001).sort((x, y) => y[1] - x[1]);
  return (
    <ul className="m-0 list-none space-y-2 p-0">
      {rows.map(([id, p]) => (
        <li key={id} className="grid grid-cols-[minmax(0,14rem)_1fr_3rem] items-center gap-3 text-sm">
          <span>{labels[id] ?? id}</span>
          <span className="h-3 rounded-sm bg-basalt"><span className="block h-3 rounded-sm bg-dusk" style={{ width: `${p * 100}%` }} /></span>
          <span className="numeral text-right">{Math.round(p * 100)}%</span>
        </li>
      ))}
    </ul>
  );
}

/** The home page: you, right now. */
export function Me() {
  const me = useMe();
  if (me.isError) return <ErrorNote error={me.error} retry={() => me.refetch()} />;
  if (!me.data) return <Skeleton lines={8} height={28} />;
  return <MyHealth id={me.data.astronaut_id} name={me.data.name} role={me.data.role} />;
}

function MyHealth({ id, name, role }: { id: string; name: string; role: string }) {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "long" ? "long" : "now";
  const setTab = (next: "now" | "long") => setParams((prev) => {
    const p = new URLSearchParams(prev);
    if (next === "long") p.set("tab", "long"); else p.delete("tab");
    return p;
  }, { replace: true });
  const a = useAssessment(id);
  const vitals = useVitals(id);
  const timeline = useTimeline(id);
  const daily = useDaily(id);
  const reminders = useReminders(id);
  const cards = useIndicators();
  const meta = useMeta();

  if (a.isError) return <ErrorNote error={a.error} retry={() => a.refetch()} />;
  if (!a.data) return <Skeleton lines={8} height={28} />;
  const d = a.data;
  const lim = meta.data?.limits;
  const hourly: Series[] = [
    { key: "heart_rate", label: "Heart rate", unit: "bpm" },
    { key: "spo2", label: "Blood oxygen", unit: "%" },
    { key: "core_temp", label: "Body temperature", unit: "°C" },
    { key: "systolic_bp", second: "diastolic_bp", label: "Blood pressure", unit: "mmHg" },
    { key: "resp_rate", label: "Breathing rate", unit: "per min" },
    { key: "hrv_rmssd", label: "Heart rate variability", unit: "ms" },
    { key: "pvt_reaction_ms", label: "Reaction time", unit: "ms" },
    { key: "cabin_co2_mmhg", label: "Cabin CO2", unit: "mmHg", limit: lim?.cabin_co2_1h_mmhg, limitLabel: "1-hour limit" },
    { key: "radiation_ugy_per_day", label: "Radiation dose rate", unit: "µGy/day" },
  ];
  const due = reminders.data?.items.filter((i) => i.status === "due") ?? [];

  return (
    <div className="space-y-6">

      <section className="panel grid gap-6 p-6 md:grid-cols-[1fr_auto]" style={{ borderLeft: `6px solid ${LEVEL_COLOR[d.status]}` }}>
        <div>
          <StatusChip level={d.status} large />
          <h1 className="mt-2 text-3xl">{name}</h1>
          <p className="text-sm text-dust-dim">{role}, sol {d.mission_day}, as of {when(d.timestamp)}</p>
          <p className="display mt-4 text-xl">{d.alerts[0]?.message ?? d.condition_label}</p>
          <p className="mt-1 max-w-[68ch] text-lg">{d.alerts[0]?.reason ?? "Every indicator is within your own normal range and inside the clinical limits."}</p>
        </div>
        <div className="text-center">
          <Gauge score={d.health_score} color={LEVEL_COLOR[d.status]} />
          <p className="text-sm text-dust-dim">health score</p>
          <p className="mt-2 text-sm text-dust-dim" title="Share of real training days that were less unusual than today">today is more unusual than {Math.round(d.anomaly_score * 100)}% of ordinary days</p>
        </div>
      </section>

      <EscalationCard escalation={d.escalation} />

      <div className="flex gap-2" role="tablist" aria-label="View">
        <button role="tab" aria-selected={tab === "now"} aria-pressed={tab === "now"} className="btn-quiet" onClick={() => setTab("now")}>Now</button>
        <button role="tab" aria-selected={tab === "long"} aria-pressed={tab === "long"} className="btn-quiet" onClick={() => setTab("long")}>Long-term risk</button>
      </div>

      {tab === "long" ? <LongTerm astronautId={id} /> : (
        <>
          <Panel title="What to do now" aside={d.actions.length ? "Most urgent first. Ticks are only for you; nothing is sent." : undefined}>
            <ActionChecklist actions={d.actions} />
          </Panel>

          <div className="grid gap-6 lg:grid-cols-2">
            <Panel title="Your body">
              <BodyFigure systems={d.body_systems} cards={cards.data} />
            </Panel>
            <Panel title={d.alerts.length ? `Why: ${d.alerts.length} alert${d.alerts.length > 1 ? "s" : ""}` : "Why"}>
              {d.alerts.length === 0
                ? <p className="text-base">No alerts. The engine checks clinical limits, your own baselines, cabin air and radiation every hour.</p>
                : <ul className="m-0 list-none space-y-4 p-0">{d.alerts.map((x, i) => <AlertItem key={i} alert={x} />)}</ul>}
              {d.drivers.length > 0 && (
                <p className="mt-5 text-sm text-dust-dim">
                  Furthest from your own normal today: {d.drivers.map((x) => `${x.signal.replace("_", " ")} (${signed(x.z)} SD)`).join(", ")}. Positive means worse.
                </p>
              )}
            </Panel>
          </div>

          <Panel title="Every indicator against your own normal">
            <Readings a={d} />
          </Panel>

          <Panel title="Last 72 hours">
            {vitals.isError ? <ErrorNote error={vitals.error} retry={() => vitals.refetch()} />
              : vitals.data && timeline.data ? <HourlyCharts rows={vitals.data} timeline={timeline.data} series={hourly} /> : <Skeleton lines={5} height={24} />}
          </Panel>

          <Panel title="Last 30 sols">
            {daily.isError ? <ErrorNote error={daily.error} retry={() => daily.refetch()} />
              : !daily.data ? <Skeleton lines={5} height={24} />
              : daily.data.length === 0 ? <p>No daily check-ins yet. They start after the first night of the mission.</p>
              : <DailyCharts rows={daily.data} series={DAILY} />}
          </Panel>

          <div className="grid gap-6 lg:grid-cols-2">
            <Panel title="Daily plan">
              <ul className="m-0 list-disc space-y-2 pl-5 text-base">{d.daily_plan.map((p, i) => <li key={i}>{p.action}</li>)}</ul>
              <h3 className="mt-5 text-base text-dust-dim">Measurements</h3>
              {reminders.data ? (
                <>
                  <p className="text-base">{due.length ? `${due.length} due now.` : "Nothing due right now."} Check-in streak: <span className="numeral text-xl">{reminders.data.checkin_streak_days}</span> sols.</p>
                  <ul className="m-0 mt-2 list-none space-y-1 p-0 text-sm">
                    {reminders.data.items.map((i) => (
                      <li key={i.id} className="flex gap-3">
                        <span className="w-20 shrink-0" style={{ color: i.status === "due" ? "var(--color-dusk)" : "var(--color-dust-dim)" }}>{i.status === "due" ? "Due now" : i.status === "done" ? "Done" : "Later"}</span>
                        <span>{i.label}</span>
                      </li>
                    ))}
                  </ul>
                </>
              ) : <Skeleton lines={3} />}
            </Panel>
            <Panel title="How the evidence splits" aside="Relative weight per condition, not a probability">
              <Evidence a={d} />
            </Panel>
          </div>

          <Panel title="Measurement check-in">
            <CheckIn astronautId={id} />
          </Panel>
          <p className="max-w-[78ch] text-sm text-dust-dim">{d.disclaimer}</p>
        </>
      )}
    </div>
  );
}
