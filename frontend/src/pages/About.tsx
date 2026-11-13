import { useCases, useMeta, useMission } from "../api/hooks";
import { ErrorNote, Panel, Skeleton, SourceBadge, when } from "../components/ui";

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
      <div>
        <h1 className="text-2xl">Data and sources</h1>
        <p className="mt-1 max-w-[72ch] text-base text-dust-dim">
          NASA publishes no daily vitals for astronauts. So real data sets the statistics, a generator builds a fictional astronaut with those statistics, and the engine runs on that astronaut.
          Nothing simulated is shown as real: every value carries one of these two badges.
        </p>
      </div>

      <Panel title="Real measurements" aside={<SourceBadge source={{ kind: "real" }} />}>
        <ul className="m-0 list-disc space-y-1 pl-5 text-base">
          {real.map(([key, s]) => <li key={key}>{nameOf(key)}: {s.dataset}</li>)}
        </ul>
        {mission.data?.radiation_replay && (
          <p className="mt-3 max-w-[72ch] text-sm text-dust-dim">
            The radiation series is Curiosity's RAD instrument on the Mars surface, {when(mission.data.radiation_replay.from)} to {when(mission.data.radiation_replay.to)} 2024, replayed hour for hour.
            It includes the solar storm of 20 May 2024. It is a real measurement, but not a dosimeter worn by a person.
          </p>
        )}
      </Panel>

      <Panel title="Simulated, calibrated on real data" aside={<SourceBadge source={{ kind: "simulated" }} />}>
        <dl className="grid gap-x-8 gap-y-4 md:grid-cols-2">
          {[...byCalibration.entries()].map(([on, keys]) => (
            <div key={on}>
              <dt className="display text-base">{on}</dt>
              <dd className="m-0 text-base text-dust-dim">{keys.join(", ")}</dd>
            </div>
          ))}
        </dl>
        {mission.data?.cabin_co2_source && (
          <p className="mt-3 max-w-[72ch] text-sm text-dust-dim">
            Cabin CO2 resamples real ISS mission {mission.data.cabin_co2_source.base}; the planted high-CO2 stretch comes from {mission.data.cabin_co2_source.planted_high}.
          </p>
        )}
      </Panel>

      <Panel title="Citations">
        <ul className="m-0 list-disc space-y-2 pl-5 text-base">
          {meta.data.citations.map((c) => <li key={c} className="max-w-[78ch]">{c}</li>)}
        </ul>
      </Panel>

      <Panel title="The planted test cases" aside="Ground truth, used only to check the engine">
        {cases.data ? (
          <ul className="m-0 list-none space-y-4 p-0">
            {cases.data.map((c) => (
              <li key={c.id}>
                <h3 className="text-base">{c.title} <span className="text-sm font-normal text-dust-dim">from {when(c.start)}, {c.affects}</span></h3>
                <p className="max-w-[78ch] text-sm">Planted: {c.planted}.</p>
                <p className="max-w-[78ch] text-sm text-dust-dim">Expected: {c.expected}.</p>
              </li>
            ))}
          </ul>
        ) : <Skeleton lines={4} />}
      </Panel>

      <Panel title="How the engine was checked">
        <ul className="m-0 list-disc space-y-2 pl-5 text-base">
          <li className="max-w-[78ch]">On 14 real people (PMData) the body models raise 1.00 false alarm per person per month. Detection was measured on changes planted into those real series: slow heart-rate drifts are caught in 74% of cases within about 6 days; subtle combinations in about half.</li>
          <li className="max-w-[78ch]">On 35 months of real Mars radiation data the storm alarm caught the 20 May 2024 storm in its first hour and raised no unconfirmed alarm.</li>
          <li className="max-w-[78ch]">The cabin rule was replayed on 468 days of real ISS CO2.</li>
          <li className="max-w-[78ch]">Blood pressure, blood oxygen, temperature and blood sugar exist in none of these datasets. They are simulated, and their limits are standard clinical thresholds that were not tested on data.</li>
        </ul>
        <p className="mt-3 text-sm text-dust-dim">Full numbers and the notebooks behind them: docs/MODELS.md and notebooks/ in the repository.</p>
      </Panel>
    </div>
  );
}
