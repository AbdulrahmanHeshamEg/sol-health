import { BookMarked, CheckCheck, Database, FlaskConical, Target } from "lucide-react";
import { useCases, useMeta, useMission } from "../api/hooks";
import { Card, ErrorNote, PageHeader, Skeleton, SourceBadge, when } from "../components/ui";

// Display names for the source keys the API reports (data/demo/sources.json).
const NAMES: Record<string, string> = {
  resting_hr: "resting heart rate", sleep_minutes: "sleep", heart_rate: "heart rate", cabin_co2_mmhg: "cabin CO2",
  radiation_ugy_per_day: "radiation dose rate", radiation_msv: "radiation dose (mSv, quality factor 3.0)",
  systolic_bp: "blood pressure (upper)", diastolic_bp: "blood pressure (lower)", spo2: "blood oxygen", core_temp: "body temperature",
  resp_rate: "breathing rate", hrv_rmssd: "heart rate variability", pvt_reaction_ms: "reaction time", fluid_intake_ml: "fluid intake",
  blood_glucose_mg_dl: "blood sugar", headache: "headache reports",
};
const nameOf = (key: string) => NAMES[key] ?? key.replace(/_/g, " ");

export function About() {
  const meta = useMeta();
  const mission = useMission();
  const cases = useCases();
  if (meta.isError) return <ErrorNote error={meta.error} retry={() => meta.refetch()} />;
  if (!meta.data) return <Skeleton lines={8} height={24} />;
  const sources = Object.entries(meta.data.sources);
  const real = sources.filter(([, s]) => s.kind === "real");
  const simulated = sources.filter(([, s]) => s.kind === "simulated");
  const byCalibration = new Map<string, string[]>();
  for (const [key, s] of simulated) byCalibration.set(s.calibrated_on ?? "other", [...(byCalibration.get(s.calibrated_on ?? "other") ?? []), nameOf(key)]);

  return (
    <div className="space-y-6">
      <PageHeader title="Data and sources"
        subtitle="NASA publishes no daily vitals for astronauts. So real data sets the statistics, a generator builds a fictional astronaut with those statistics, and the engine runs on that astronaut. Nothing simulated is shown as real: every value carries one of these two badges." />

      <div className="grid items-start gap-6 lg:grid-cols-2">
        <Card title="Real measurements" icon={<Database size={18} />} aside={<SourceBadge source={{ kind: "real" }} />}>
          <ul className="m-0 list-none space-y-2 p-0 text-sm">
            {real.map(([key, s]) => (
              <li key={key} className="flex justify-between gap-4 border-b border-line pb-2 last:border-0 last:pb-0">
                <span className="font-medium">{nameOf(key)}</span><span className="text-right text-ink-3">{s.dataset}</span>
              </li>
            ))}
          </ul>
          {mission.data?.radiation_replay && (
            <p className="mt-4 text-sm text-ink-3">
              The radiation series is Curiosity's RAD instrument on the Mars surface, {when(mission.data.radiation_replay.from)} to {when(mission.data.radiation_replay.to)} 2024, replayed hour for hour.
              It includes the solar storm of 20 May 2024. It is a real measurement, but not a dosimeter worn by a person.
            </p>
          )}
        </Card>

        <Card title="Simulated, calibrated on real data" icon={<FlaskConical size={18} />} aside={<SourceBadge source={{ kind: "simulated" }} />}>
          <dl className="m-0 space-y-3">
            {[...byCalibration.entries()].map(([on, keys]) => (
              <div key={on} className="rounded-xl bg-surface-2 p-3">
                <dt className="text-sm font-semibold">{on}</dt>
                <dd className="m-0 mt-1 text-sm text-ink-3">{keys.join(", ")}</dd>
              </div>
            ))}
          </dl>
          {mission.data?.cabin_co2_source && (
            <p className="mt-4 text-sm text-ink-3">
              Cabin CO2 resamples real ISS mission {mission.data.cabin_co2_source.base}; the planted high-CO2 stretch comes from {mission.data.cabin_co2_source.planted_high}.
            </p>
          )}
        </Card>
      </div>

      <Card title="How the engine was checked" icon={<CheckCheck size={18} />}>
        <ul className="m-0 grid list-none gap-3 p-0 md:grid-cols-2">
          {[
            ["1.00 false alarm per person-month", "On 14 real people (PMData). Slow heart-rate drifts planted into those real series are caught in 74% of cases within about 6 days; subtle combinations in about half."],
            ["Storm caught in its first hour", "On 35 months of real Mars radiation data the storm alarm caught the 20 May 2024 storm in its first hour and raised no unconfirmed alarm."],
            ["468 days of real ISS air", "The cabin CO2 rule was replayed on 468 days of real ISS measurements."],
            ["Clinical limits, not tested on data", "Blood pressure, blood oxygen, temperature and blood sugar exist in none of these datasets. They are simulated, and their limits are standard clinical thresholds."],
          ].map(([title, text]) => (
            <li key={title} className="rounded-xl border border-line p-4">
              <p className="font-semibold">{title}</p>
              <p className="mt-1 text-sm text-ink-2">{text}</p>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-xs text-ink-3">Full numbers and the notebooks behind them: docs/MODELS.md and notebooks/ in the repository.</p>
      </Card>

      <Card title="The planted test cases" icon={<Target size={18} />} aside="Ground truth, used only to check the engine">
        {cases.data ? (
          <ul className="m-0 grid list-none gap-3 p-0 md:grid-cols-2">
            {cases.data.map((c) => (
              <li key={c.id} className="rounded-xl border border-line p-4">
                <p className="font-semibold">{c.title}</p>
                <p className="mt-0.5 text-xs text-ink-3">From {when(c.start)} · {c.affects}</p>
                <p className="mt-2 text-sm"><span className="font-medium">Planted:</span> {c.planted}.</p>
                <p className="mt-1 text-sm text-ink-3"><span className="font-medium">Expected:</span> {c.expected}.</p>
              </li>
            ))}
          </ul>
        ) : <Skeleton lines={4} />}
      </Card>

      <Card title="Citations" icon={<BookMarked size={18} />}>
        <ol className="m-0 list-decimal space-y-2 pl-5 text-sm text-ink-2">
          {meta.data.citations.map((c) => <li key={c}>{c}</li>)}
        </ol>
      </Card>
    </div>
  );
}
