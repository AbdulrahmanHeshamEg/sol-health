// Today's questions, asked by the engine. The app only shows them; answers go back to the engine and are kept on this device.
import { useState } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useQuestions } from "../api/hooks";
import type { Question, QuestionGroup } from "../api/types";
import { useLinkWithAt, useReplay } from "../state/replay";
import { ErrorNote, Skeleton } from "./ui";

function Field({ q, value, onChange }: { q: Question; value: number | undefined; onChange: (v: number | undefined) => void }) {
  if (q.type === "number") {
    return (
      <label className="mt-2 flex items-center gap-2">
        <input className="field max-w-[10rem]" type="number" inputMode="decimal" min={q.min} max={q.max} step={q.step}
          value={value ?? ""} placeholder={q.answer !== null ? String(q.answer) : ""}
          onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))} aria-label={q.text} />
        {q.unit && <span className="text-sm text-dust-dim">{q.unit}</span>}
      </label>
    );
  }
  const current = value ?? q.answer ?? undefined;
  return (
    <div className="mt-2 flex flex-wrap gap-2" role="radiogroup" aria-label={q.text}>
      {q.options!.map((o) => (
        <button key={o.value} type="button" role="radio" aria-checked={current === o.value} aria-pressed={current === o.value}
          className="btn-quiet text-sm" onClick={() => onChange(current === o.value && value !== undefined ? undefined : o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

function Group({ group, astronautId }: { group: QuestionGroup; astronautId: string }) {
  const { at } = useReplay();
  const link = useLinkWithAt();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Record<string, number>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const open = group.questions.filter((q) => !q.answered).length;
  const changed = Object.keys(draft).length;

  async function save() {
    setBusy(true); setError(null); setSaved(null);
    try {
      const a = await api.answer(astronautId, draft, at);
      setDraft({});
      setSaved(a.alerts[0] ? `Saved. ${a.alerts[0].reason}` : "Saved. Everything is within your normal range.");
      await queryClient.invalidateQueries();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Your answers were not saved.");
    } finally { setBusy(false); }
  }

  return (
    <section className="border-t border-line pt-4 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-base">{group.title}{group.optional ? " (optional)" : ""}</h3>
        <span className="text-sm text-dust-dim">{open ? `${open} open` : "All answered"}</span>
      </div>
      <ol className="m-0 mt-2 list-none space-y-4 p-0">
        {group.questions.map((q) => (
          <li key={q.field}>
            {q.trigger && <p className="text-xs text-dusk">Because: {q.trigger.toLowerCase()}</p>}
            <p className="text-base">{q.text} {q.answered && <span className="text-sm text-dust-dim">(answered: {String(q.answer)})</span>}</p>
            <p className="text-sm text-dust-dim">{q.why}</p>
            {q.type === "photo"
              ? <Link to={link("/eyes")} className="btn mt-2 inline-block text-sm no-underline">Upload your eye photo</Link>
              : <Field q={q} value={draft[q.field]} onChange={(v) => setDraft((d) => {
                  const next = { ...d };
                  if (v === undefined) delete next[q.field]; else next[q.field] = v;
                  return next;
                })} />}
          </li>
        ))}
      </ol>
      {group.questions.some((q) => q.type !== "photo") && (
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button className="btn" disabled={!changed || busy} onClick={save}>{busy ? "Saving" : changed ? `Save ${changed} answer${changed > 1 ? "s" : ""}` : "Save answers"}</button>
          {saved && <p className="text-sm" aria-live="polite">{saved}</p>}
        </div>
      )}
      {error && <p role="alert" className="mt-3 max-w-[70ch] rounded-sm border border-line p-3 text-sm">{error}</p>}
    </section>
  );
}

export function QuestionsPanel({ astronautId }: { astronautId: string }) {
  const q = useQuestions(astronautId);
  if (q.isError) return <ErrorNote error={q.error} retry={() => q.refetch()} />;
  if (!q.data) return <Skeleton lines={5} />;
  return (
    <div>
      <p className="mb-4 text-sm text-dust-dim">
        {q.data.answered} of {q.data.total} answered today. Your answers replace the simulated values and the engine reads them at once.
      </p>
      <div className="space-y-5">{q.data.groups.map((g) => <Group key={g.id} group={g} astronautId={astronautId} />)}</div>
    </div>
  );
}
