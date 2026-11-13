// Manual measurement check-in. The values go to the engine (POST /api/assess); the engine decides what they mean.
import { useState } from "react";
import { api } from "../api/client";
import type { Assessment, CheckIn as CheckInValues } from "../api/types";
import { useReplay } from "../state/replay";
import { StatusChip } from "./ui";

const NUMBERS: Array<{ key: keyof CheckInValues; label: string; unit: string; step: number }> = [
  { key: "systolic_bp", label: "Blood pressure, upper", unit: "mmHg", step: 1 },
  { key: "diastolic_bp", label: "Blood pressure, lower", unit: "mmHg", step: 1 },
  { key: "blood_glucose_mg_dl", label: "Fasting blood sugar", unit: "mg/dL", step: 1 },
  { key: "core_temp", label: "Body temperature", unit: "°C", step: 0.1 },
  { key: "sleep_hours", label: "Sleep last night", unit: "hours", step: 0.25 },
];
const SCORES: Array<{ key: "mood" | "stress" | "fatigue"; label: string; low: string; high: string }> = [
  { key: "mood", label: "Mood", low: "very low", high: "very good" },
  { key: "stress", label: "Stress", low: "very stressed", high: "relaxed" },
  { key: "fatigue", label: "Energy", low: "exhausted", high: "fresh" },
];

export function CheckIn({ astronautId, name }: { astronautId: string; name: string }) {
  const { at } = useReplay();
  const [values, setValues] = useState<CheckInValues>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Assessment | null>(null);
  const filled = Object.keys(values).length > 0;

  const set = (key: keyof CheckInValues, v: number | boolean | undefined) =>
    setValues((prev) => {
      const next = { ...prev } as Record<string, number | boolean>;
      if (v === undefined || (typeof v === "number" && Number.isNaN(v))) delete next[key]; else next[key] = v;
      return next as CheckInValues;
    });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try { setResult(await api.checkin(astronautId, values, at)); }
    catch (err) { setResult(null); setError(err instanceof Error ? err.message : "The check-in could not be assessed."); }
    finally { setBusy(false); }
  }

  return (
    <form onSubmit={submit}>
      <p className="max-w-[64ch] text-sm text-dust-dim">
        Enter what you measured. Leave the rest empty. The engine reads your entry on top of {name.split(" ")[0]}'s latest data and answers below; nothing is saved.
      </p>
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {NUMBERS.map((f) => (
          <label key={f.key} className="block text-sm">
            {f.label} <span className="text-dust-dim">({f.unit})</span>
            <input className="field mt-1" type="number" inputMode="decimal" step={f.step}
              value={(values[f.key] as number | undefined) ?? ""} onChange={(e) => set(f.key, e.target.value === "" ? undefined : Number(e.target.value))} />
          </label>
        ))}
        <fieldset className="m-0 border-0 p-0 text-sm">
          <legend className="p-0">Headache today</legend>
          <div className="mt-1 flex gap-2">
            {[["Yes", true], ["No", false]].map(([label, v]) => (
              <button type="button" key={String(label)} className="btn-quiet" aria-pressed={values.headache === v}
                onClick={() => set("headache", values.headache === v ? undefined : (v as boolean))}>{label as string}</button>
            ))}
          </div>
        </fieldset>
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        {SCORES.map((s) => (
          <fieldset key={s.key} className="m-0 border-0 p-0 text-sm">
            <legend className="p-0">{s.label} <span className="text-dust-dim">(1 = {s.low}, 5 = {s.high})</span></legend>
            <div className="mt-1 flex gap-2">
              {[1, 2, 3, 4, 5].map((n) => (
                <button type="button" key={n} className="btn-quiet numeral w-10" aria-pressed={values[s.key] === n} aria-label={`${s.label} ${n} of 5`}
                  onClick={() => set(s.key, values[s.key] === n ? undefined : n)}>{n}</button>
              ))}
            </div>
          </fieldset>
        ))}
      </div>
      <div className="mt-5 flex flex-wrap items-center gap-4">
        <button className="btn" type="submit" disabled={!filled || busy}>{busy ? "Assessing" : "Assess my check-in"}</button>
        {filled && <button type="button" className="btn-quiet" onClick={() => { setValues({}); setResult(null); setError(null); }}>Clear the form</button>}
      </div>
      {error && <p role="alert" className="mt-4 max-w-[70ch] rounded-sm border border-line p-3 text-sm">{error}</p>}
      {result && (
        <div className="mt-5 rounded-sm bg-basalt p-4" aria-live="polite">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <StatusChip level={result.status} large />
            <p className="display text-lg">{result.condition_label}</p>
            <p className="text-sm text-dust-dim">with your check-in applied; score {result.health_score}/100</p>
          </div>
          {result.alerts.length === 0
            ? <p className="mt-2 text-base">Nothing in this check-in is outside your normal range or a clinical limit.</p>
            : <ul className="mt-2 list-disc space-y-1 pl-5 text-base">{result.alerts.map((a, i) => <li key={i}>{a.reason}</li>)}</ul>}
          {result.actions.length > 0 && <p className="mt-3 text-base"><span className="font-bold">First step:</span> {result.actions[0].action}</p>}
        </div>
      )}
    </form>
  );
}
