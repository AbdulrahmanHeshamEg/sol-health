// The daily brief: a short read of your day and what to do about it. Written by rules today; an AI model will fill the same card later.
import { useBrief } from "../api/hooks";
import { ErrorNote, LEVEL_COLOR, Skeleton } from "./ui";

export function DailyBrief({ astronautId }: { astronautId: string }) {
  const b = useBrief(astronautId);
  if (b.isError) return <ErrorNote error={b.error} retry={() => b.refetch()} />;
  if (!b.data) return <Skeleton lines={4} />;
  const d = b.data;
  return (
    <section className="panel p-5" aria-labelledby="brief-title">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="brief-title" className="text-lg">Your day</h2>
        <span className="text-xs text-dust-dim" title={d.generated_by.note}>{d.generated_by.label}</span>
      </div>
      <p className="display mt-2 text-xl" style={{ color: d.status === "GREEN" ? undefined : LEVEL_COLOR[d.status] }}>{d.headline}</p>
      <div className="mt-2 max-w-[72ch] space-y-2 text-base">{d.paragraphs.map((p, i) => <p key={i}>{p}</p>)}</div>
      {d.changes.length > 0 && (
        <>
          <h3 className="mt-4 text-base text-dust-dim">Compared with your last week</h3>
          <ul className="m-0 mt-1 list-none space-y-1 p-0 text-base">
            {d.changes.map((c) => (
              <li key={c.label}><span aria-hidden="true" className="mr-2" style={{ color: c.direction === "worse" ? LEVEL_COLOR.YELLOW : LEVEL_COLOR.GREEN }}>{c.direction === "worse" ? "▲" : "●"}</span>{c.text}</li>
            ))}
          </ul>
        </>
      )}
      <h3 className="mt-4 text-base text-dust-dim">Today's tips</h3>
      <ul className="m-0 mt-1 list-disc space-y-1 pl-5 text-base">{d.tips.map((t, i) => <li key={i} className="max-w-[70ch]">{t}</li>)}</ul>
      {d.ask_next.map((t, i) => <p key={i} className="mt-3 text-sm text-dusk">{t}</p>)}
    </section>
  );
}
