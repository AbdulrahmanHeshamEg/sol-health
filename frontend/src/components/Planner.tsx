// The day as a planner: your to-dos and a timed schedule. Everything in it comes from the engine
// (actions, reminders, the report to the flight surgeon); this file lays it out by time and lets you tick things off.
// Every day starts at zero: only your own ticks count, kept on this device for that day. Nothing is sent.
import { useMemo, useState } from "react";
import { Check, Stethoscope } from "lucide-react";
import type { Assessment, Reminders } from "../api/types";
import { isEyeAction } from "../lib/eye";
import { parseTs } from "../state/replay";
import { StatusIcon, clock } from "./ui";

function useTicks(day: string) {
  const key = `sol-done-${day}`;
  const [ticks, setTicks] = useState<Set<string>>(() => {
    try { return new Set(JSON.parse(localStorage.getItem(key) ?? "[]")); } catch { return new Set(); }
  });
  const toggle = (id: string) => setTicks((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    try { localStorage.setItem(key, JSON.stringify([...next])); } catch { /* storage blocked: ticks last this visit */ }
    return next;
  });
  return { ticks, toggle };
}

function Tick({ on, onClick, label }: { on: boolean; onClick: () => void; label: string }) {
  return (
    <button type="button" role="checkbox" aria-checked={on} aria-label={label} onClick={onClick}
      className="grid h-[22px] w-[22px] shrink-0 place-items-center rounded-full border-[1.5px] transition-colors"
      style={on ? { background: "var(--color-brand)", borderColor: "var(--color-brand)", color: "#fff" } : { borderColor: "var(--color-line-strong)" }}>
      {on && <Check size={13} strokeWidth={3} aria-hidden="true" />}
    </button>
  );
}

interface Slot { id: string; at: number; kind: "measure" | "checkin" | "appointment"; title: string; note?: string; agenda?: string[]; due?: boolean }


export function Planner({ a, reminders, onCheckIn }: { a: Assessment; reminders?: Reminders; onCheckIn: () => void }) {
  const now = parseTs(a.timestamp).getTime();
  const { ticks, toggle } = useTicks(a.timestamp.slice(0, 10));

  const todos = useMemo(() => a.actions.filter((x) => x.who === "self" && !isEyeAction(x)).sort((p, q) => p.priority - q.priority), [a.actions]);

  const slots = useMemo<Slot[]>(() => {
    const out: Slot[] = (reminders?.items ?? []).map((r) => {
      const checkin = r.id === "morning_checkin";
      return {
        id: r.id, at: parseTs(r.due_at).getTime(), kind: checkin ? "checkin" : "measure",
        title: checkin ? "Daily check-in" : r.label,
        note: checkin ? "Sleep, mood, energy, headache. About a minute." : r.logged_automatically ? "Your sensors can log this" : undefined,
        due: r.status === "due",
      };
    });
    const e = a.escalation;
    if (e.status !== "none" && e.sent_at) {
      out.push({
        id: "surgeon", at: parseTs(e.sent_at).getTime(), kind: "appointment",
        title: e.status === "sent" ? "Urgent message to your flight surgeon" : "Daily report to your flight surgeon",
        note: e.arrives_at ? `Reaches Earth at ${clock(e.arrives_at)}.${e.status === "sent" ? " Keep working through your list while you wait for the reply." : ""}` : undefined,
        agenda: a.actions.filter((x) => x.who === "ground" && !isEyeAction(x)).map((x) => x.action),
      });
    }
    return out.sort((p, q) => p.at - q.at);
  }, [reminders, a.escalation, a.actions]);

  const countable = [...todos.map((t) => `t-${t.priority}`), ...slots.filter((s) => s.kind !== "appointment").map((s) => `s-${s.id}`)];
  const finished = countable.filter((id) => ticks.has(id)).length;
  const nowIndex = slots.findIndex((s) => s.at > now);

  return (
    <section aria-label="Your plan for today">
      <div className="flex items-end justify-between gap-3 px-1">
        <h2 className="section-title">Plan for today</h2>
        <span className="tnum text-sm text-ink-3">{finished} of {countable.length} done</span>
      </div>
      <div className="mt-2 h-1 overflow-hidden rounded-full bg-surface-3"><div className="h-full rounded-full bg-brand transition-[width]" style={{ width: `${countable.length ? (finished / countable.length) * 100 : 0}%` }} /></div>

      <p className="eyebrow mt-5 px-1">To do</p>
      <ul className="card m-0 mt-1.5 list-none overflow-hidden p-0">
        {todos.length === 0 && <li className="px-4 py-3 text-sm text-ink-2">Nothing on your list today.</li>}
        {todos.map((t) => {
          const id = `t-${t.priority}`;
          const on = ticks.has(id);
          return (
            <li key={id} className="flex items-start gap-3 py-3 pl-4">
              <span className="pt-0.5"><Tick on={on} onClick={() => toggle(id)} label={t.action} /></span>
              <div className="min-w-0 flex-1 border-b border-line pb-3 pr-4 [li:last-child_&]:border-0 [li:last-child_&]:pb-0">
                <div className="flex items-start gap-2">
                  <p className="flex-1 text-[0.95rem]" style={on ? { color: "var(--color-ink-3)" } : undefined}>{t.action}</p>
                  <StatusIcon level={t.level} size={15} />
                </div>
              </div>
            </li>
          );
        })}
      </ul>

      <p className="eyebrow mt-5 px-1">Schedule</p>
      <ol className="card m-0 mt-1.5 list-none p-0 py-1">
        {slots.map((s, i) => (
          <li key={s.id}>
            {i === nowIndex && <NowLine now={now} />}
            {s.kind === "appointment"
              ? <Appointment s={s} />
              : <SlotRow s={s} on={ticks.has(`s-${s.id}`)} toggle={() => toggle(`s-${s.id}`)} onCheckIn={s.kind === "checkin" ? onCheckIn : undefined} />}
          </li>
        ))}
        {nowIndex === -1 && slots.length > 0 && <li><NowLine now={now} /></li>}
      </ol>

    </section>
  );
}

function NowLine({ now }: { now: number }) {
  return (
    <div className="flex items-center gap-2 px-4 py-1" aria-label="Now">
      <span className="tnum w-11 shrink-0 text-xs font-semibold" style={{ color: "var(--color-bad)" }}>{clock(new Date(now).toISOString())}</span>
      <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: "var(--color-bad)" }} aria-hidden="true" />
      <span className="h-px flex-1" style={{ background: "var(--color-bad)", opacity: 0.45 }} aria-hidden="true" />
    </div>
  );
}

function SlotRow({ s, on, toggle, onCheckIn }: { s: Slot; on: boolean; toggle: () => void; onCheckIn?: () => void }) {
  return (
    <div className="flex items-start gap-3 px-4 py-2.5">
      <span className="tnum w-11 shrink-0 pt-0.5 text-xs font-medium text-ink-3">{clock(new Date(s.at).toISOString())}</span>
      <Tick on={on} onClick={toggle} label={s.title} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <p className="text-[0.95rem]" style={on ? { color: "var(--color-ink-3)" } : undefined}>{s.title}</p>
          {s.due && !on && <span className="rounded-full px-2 py-px text-[0.7rem] font-semibold" style={{ background: "var(--color-warn-soft)", color: "var(--color-warn-ink)" }}>Due</span>}
        </div>
        {s.note && <p className="mt-0.5 text-xs text-ink-3">{s.note}</p>}
        {onCheckIn && !on && <button className="btn mt-2 px-3 py-1 text-xs" onClick={onCheckIn}>Start check-in</button>}
      </div>
    </div>
  );
}

function Appointment({ s }: { s: Slot }) {
  return (
    <div className="mx-2 my-1.5 flex items-start gap-3 rounded-2xl px-2 py-3" style={{ background: "var(--color-brand-soft)" }}>
      <span className="tnum w-11 shrink-0 pt-0.5 text-xs font-semibold text-brand-ink">{clock(new Date(s.at).toISOString())}</span>
      <span className="grid h-[22px] w-[22px] shrink-0 place-items-center rounded-full bg-brand text-white" aria-hidden="true"><Stethoscope size={12} /></span>
      <div className="min-w-0 flex-1">
        <p className="eyebrow" style={{ color: "var(--color-brand-ink)" }}>Appointment</p>
        <p className="text-[0.95rem] font-semibold">{s.title}</p>
        {s.note && <p className="mt-0.5 text-xs text-ink-3">{s.note}</p>}
        {s.agenda && s.agenda.length > 0 && <ul className="m-0 mt-2 list-disc space-y-1 pl-4 text-sm text-ink-2">{s.agenda.map((x, i) => <li key={i}>{x}</li>)}</ul>}
      </div>
    </div>
  );
}
