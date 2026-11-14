// The daily check-in: a few quick steps instead of a long form. The engine asks the questions (/questions) and reads
// the answers (/answers); this only picks a short set and shows one step at a time. Anything the engine flags as a
// follow-up comes first. Questions not asked here keep their simulated values.
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Camera, Check, Minus, Plus, Smile, Sparkles, X, Zap } from "lucide-react";
import { api } from "../api/client";
import { useQuestions } from "../api/hooks";
import type { Question } from "../api/types";
import { isEyeQuestion } from "../lib/eye";
import { useLinkWithAt, useReplay } from "../state/replay";
import { Skeleton } from "./ui";

/** The short set asked every day. Each entry is one step; a step can hold more than one question. */
const DAILY_STEPS: Array<{ id: string; fields: string[]; title: string; icon: React.ReactNode }> = [
  { id: "feel", fields: ["mood", "fatigue"], title: "How do you feel?", icon: <Smile size={22} /> },
  { id: "headache", fields: ["headache"], title: "Any headache today?", icon: <Zap size={22} /> },
];

interface Step { id: string; title: string; icon: React.ReactNode; questions: Question[]; followUp?: boolean }

/** Steps for today, built from what the engine asks. */
export function useCheckInSteps(astronautId: string) {
  const q = useQuestions(astronautId);
  const steps = useMemo<Step[]>(() => {
    if (!q.data) return [];
    const all = q.data.groups.flatMap((g) => g.questions.map((x) => ({ ...x, group: g.id })));
    const byField = new Map(all.map((x) => [x.field, x]));
    // Eye follow-ups belong to the monthly eye exam, so the daily check-in leaves them out.
    const followUps: Step[] = all.filter((x) => x.group === "follow_up" && !isEyeQuestion(x))
      .map((x) => ({ id: `fu-${x.field}`, title: "One more question", icon: <Sparkles size={22} />, questions: [x], followUp: true }));
    const daily: Step[] = DAILY_STEPS.map((s) => ({ ...s, questions: s.fields.map((f) => byField.get(f)).filter((x): x is NonNullable<typeof x> => !!x) }))
      .filter((s) => s.questions.length > 0);
    return [...followUps, ...daily];
  }, [q.data]);
  const asked = steps.flatMap((s) => s.questions);
  return { query: q, steps, answered: asked.filter((x) => x.answered).length, total: asked.length };
}

const shortLabel = (l: string) => l.replace(/^\d+\s*·\s*/, "");

function Choice({ q, value, onPick }: { q: Question; value: number | undefined; onPick: (v: number) => void }) {
  const opts = q.options ?? [];
  const scale = opts.length >= 5;
  return (
    <div role="radiogroup" aria-label={q.text} className={scale ? "grid grid-cols-5 gap-2" : "grid grid-cols-2 gap-3"}>
      {opts.map((o) => {
        const on = value === o.value;
        return (
          <button key={o.value} type="button" role="radio" aria-checked={on} onClick={() => onPick(o.value)}
            className="flex flex-col items-center justify-center gap-1 rounded-2xl border-2 px-1 text-center transition-colors"
            style={{
              minHeight: scale ? 76 : 64,
              borderColor: on ? "var(--color-brand)" : "var(--color-line)",
              background: on ? "var(--color-brand-soft)" : "var(--color-surface)",
              color: on ? "var(--color-brand-ink)" : "var(--color-ink)",
            }}>
            {scale && <span className="tnum text-xl font-bold">{o.value}</span>}
            <span className={scale ? "text-[0.7rem] leading-tight text-ink-3" : "text-base font-semibold"}>{shortLabel(o.label)}</span>
          </button>
        );
      })}
    </div>
  );
}

function NumberStep({ q, value, onChange }: { q: Question; value: number | undefined; onChange: (v: number) => void }) {
  const step = q.field === "sleep_hours" ? 0.5 : (q.step ?? 1);
  const v = value ?? (q.field === "sleep_hours" ? 7 : q.min ?? 0);
  const clamp = (x: number) => Math.min(q.max ?? Infinity, Math.max(q.min ?? -Infinity, Math.round(x / step) * step));
  return (
    <div>
      <div className="flex items-center justify-center gap-5">
        <button type="button" className="icon-btn h-12 w-12 rounded-full" onClick={() => onChange(clamp(v - step))} aria-label="Less"><Minus size={20} /></button>
        <p className="min-w-[7rem] text-center"><span className="tnum text-5xl font-bold">{v}</span> <span className="text-ink-3">{q.unit}</span></p>
        <button type="button" className="icon-btn h-12 w-12 rounded-full" onClick={() => onChange(clamp(v + step))} aria-label="More"><Plus size={20} /></button>
      </div>
      {q.field === "sleep_hours" && (
        <div className="mt-5 flex justify-center gap-2">
          {[5, 6, 7, 8, 9].map((h) => <button key={h} type="button" className="btn-ghost tnum" aria-pressed={v === h} onClick={() => onChange(h)}>{h}h</button>)}
        </div>
      )}
    </div>
  );
}

export function CheckInWizard({ astronautId, onClose }: { astronautId: string; onClose: () => void }) {
  const { query, steps } = useCheckInSteps(astronautId);
  const { at } = useReplay();
  const link = useLinkWithAt();
  const queryClient = useQueryClient();
  const [i, setI] = useState(0);
  const [values, setValues] = useState<Record<string, number>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState(false);
  const dialog = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", esc);
    document.body.style.overflow = "hidden";
    dialog.current?.focus();
    return () => { document.removeEventListener("keydown", esc); document.body.style.overflow = ""; };
  }, [onClose]);

  const review = i === steps.length;
  const step = steps[i];
  const valueOf = (q: Question) => values[q.field] ?? (q.answer ?? undefined);
  const set = (q: Question, v: number) => setValues((prev) => ({ ...prev, [q.field]: v }));
  const stepDone = step ? step.questions.every((q) => q.type === "photo" || valueOf(q) !== undefined) : true;
  const next = () => setI((n) => Math.min(steps.length, n + 1));

  /** A single choice moves on by itself, a moment after the tap, so the choice is seen. */
  const pick = (q: Question, v: number) => {
    set(q, v);
    const others = step.questions.filter((x) => x !== q);
    if (others.every((x) => valueOf(x) !== undefined)) window.setTimeout(next, 260);
  };

  /** Every value in the short set, whether picked now or answered earlier today. */
  const toSend = () => {
    const out: Record<string, number> = {};
    for (const s of steps) for (const q of s.questions) {
      const v = q.type === "photo" ? undefined : valueOf(q);
      if (v !== undefined) out[q.field] = v;
    }
    return out;
  };

  async function submit() {
    setBusy(true); setError(null);
    try {
      await api.answer(astronautId, toSend(), at);
      setResult(true);
      await queryClient.invalidateQueries();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Your answers were not saved.");
    } finally { setBusy(false); }
  }

  const progress = result ? 100 : (i / Math.max(1, steps.length)) * 100;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-6">
      <div className="absolute inset-0 bg-[rgb(10_15_28/0.55)] backdrop-blur-[2px]" onClick={onClose} />
      <div ref={dialog} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="checkin-title"
        className="relative flex max-h-[100dvh] w-full flex-col overflow-hidden rounded-t-3xl bg-surface shadow-[var(--shadow-pop)] outline-none sm:max-w-lg sm:rounded-3xl">
        <div className="h-1 bg-surface-3"><div className="h-full bg-brand transition-[width] duration-300" style={{ width: `${progress}%` }} /></div>
        <div className="flex items-center justify-between gap-3 px-5 pt-4">
          <p id="checkin-title" className="text-sm font-semibold text-ink-2">
            Daily check-in{!result && steps.length > 0 && <span className="font-normal text-ink-3"> · {review ? "Review" : `Step ${i + 1} of ${steps.length}`}</span>}
          </p>
          <button className="icon-btn h-9 w-9 border-0" onClick={onClose} aria-label="Close the check-in"><X size={18} /></button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 pb-6 pt-4">
          {query.isError ? <p className="text-sm">{query.error instanceof Error ? query.error.message : "The questions could not be loaded."}</p>
            : !query.data ? <Skeleton lines={4} height={22} />
            : result ? (
              /* ---------- saved ---------- */
              <div key="saved" className="step-in py-4 text-center">
                <span className="mx-auto grid h-16 w-16 place-items-center rounded-full" style={{ background: "var(--color-ok-soft)", color: "var(--color-ok-ink)" }}>
                  <Check size={30} strokeWidth={2.6} aria-hidden="true" />
                </span>
                <h2 className="mt-4 text-xl font-bold">Saved. Thanks!</h2>
                <p className="mx-auto mt-2 max-w-[38ch] text-sm text-ink-2">Your check-in for today is in. You can change it any time today.</p>
                <button className="btn mt-6 w-full" onClick={onClose}>Done</button>
              </div>
            ) : review ? (
              /* ---------- review ---------- */
              <div key="review" className="step-in">
                <h2 className="text-xl font-bold">Check your answers</h2>
                <p className="mt-1 text-sm text-ink-3">Tap an answer to change it.</p>
                <ul className="m-0 mt-5 list-none divide-y divide-line rounded-2xl border border-line p-0">
                  {steps.flatMap((s, si) => s.questions.filter((q) => q.type !== "photo").map((q) => {
                    const v = valueOf(q);
                    const label = v === undefined ? "–" : q.options ? shortLabel(q.options.find((o) => o.value === v)?.label ?? String(v)) : `${v} ${q.unit ?? ""}`;
                    return (
                      <li key={q.field} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                        <span className="text-ink-2">{q.text}</span>
                        <button className="shrink-0 border-0 bg-transparent p-0 font-semibold text-brand-ink" onClick={() => setI(si)} aria-label={`Change: ${q.text}`}>{label}</button>
                      </li>
                    );
                  }))}
                </ul>
                {error && <p role="alert" className="mt-4 rounded-xl border border-line bg-surface-2 p-3 text-sm">{error}</p>}
              </div>
            ) : step ? (
              /* ---------- one step ---------- */
              <div key={step.id} className="step-in">
                <span className="grid h-12 w-12 place-items-center rounded-2xl" style={step.followUp
                  ? { background: "var(--color-warn-soft)", color: "var(--color-warn-ink)" } : { background: "var(--color-brand-soft)", color: "var(--color-brand-ink)" }}>
                  {step.icon}
                </span>
                <h2 className="mt-4 text-2xl font-bold tracking-tight">{step.followUp ? step.questions[0].text : step.title}</h2>
                {step.followUp && step.questions[0].trigger && <p className="mt-1 text-sm text-warn-ink">Because: {step.questions[0].trigger.toLowerCase()}</p>}
                <div className="mt-6 space-y-6">
                  {step.questions.map((q) => (
                    <div key={q.field}>
                      {step.questions.length > 1 && <p className="mb-2 text-sm font-medium">{q.text}</p>}
                      {q.type === "photo" ? (
                        <Link to={link("/body?tab=eyes")} onClick={onClose} className="btn w-full"><Camera size={16} />Take your eye photo</Link>
                      ) : q.type === "number" ? (
                        <NumberStep q={q} value={valueOf(q)} onChange={(v) => set(q, v)} />
                      ) : (
                        <Choice q={q} value={valueOf(q)} onPick={(v) => pick(q, v)} />
                      )}
                    </div>
                  ))}
                </div>
                <p className="mt-6 text-xs text-ink-3">{step.questions[0].why}</p>
              </div>
            ) : (
              <p className="text-sm text-ink-2">No questions today.</p>
            )}
        </div>

        {query.data && !result && steps.length > 0 && (
          <div className="flex items-center gap-3 border-t border-line px-5 py-4">
            <button className="btn-ghost" onClick={() => setI((n) => Math.max(0, n - 1))} disabled={i === 0} style={i === 0 ? { visibility: "hidden" } : undefined}>
              <ArrowLeft size={15} />Back
            </button>
            <div className="ml-auto">
              {review
                ? <button className="btn" onClick={submit} disabled={busy}><Check size={16} />{busy ? "Saving…" : "Send"}</button>
                : <button className="btn" onClick={() => {
                    if (step?.questions.some((q) => q.type === "number" && valueOf(q) === undefined)) step.questions.forEach((q) => q.type === "number" && valueOf(q) === undefined && set(q, q.field === "sleep_hours" ? 7 : q.min ?? 0));
                    next();
                  }} disabled={!stepDone && !step?.questions.every((q) => q.type === "number" || q.type === "photo")}>
                    {step?.questions.every((q) => q.type === "photo") ? "Skip" : "Next"}<ArrowRight size={16} />
                  </button>}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
