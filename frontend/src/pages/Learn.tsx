import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { ChevronDown, Search } from "lucide-react";
import { useIndicators } from "../api/hooks";
import { ErrorNote, PageHeader, Skeleton, SourceBadge } from "../components/ui";

export function Learn() {
  const cards = useIndicators();
  const { hash } = useLocation();
  const [q, setQ] = useState("");
  useEffect(() => {
    if (cards.data && hash) document.getElementById(hash.slice(1))?.scrollIntoView({ block: "start" });
  }, [cards.data, hash]);
  if (cards.isError) return <ErrorNote error={cards.error} retry={() => cards.refetch()} />;
  if (!cards.data) return <Skeleton lines={8} height={26} />;
  const needle = q.trim().toLowerCase();
  const shown = needle ? cards.data.filter((c) => `${c.label} ${c.hazard_names.join(" ")} ${c.why}`.toLowerCase().includes(needle)) : cards.data;

  return (
    <div className="space-y-6">
      <PageHeader title="What we measure, and why"
        subtitle="For each indicator: whether it can be measured in space, why it matters, how spaceflight changes it, when your flight surgeon needs to know, and how to prevent trouble."
        aside={
          <label className="relative block w-72 max-w-full">
            <span className="sr-only">Search indicators</span>
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-3" aria-hidden="true" />
            <input className="field pl-9" placeholder="Search indicators" value={q} onChange={(e) => setQ(e.target.value)} />
          </label>
        } />
      {shown.length === 0 && <p className="text-sm text-ink-3">Nothing matches "{q}".</p>}
      <div className="grid gap-3">
        {shown.map((c) => (
          <details key={c.id} id={c.id} className="card group scroll-mt-24" open={hash === `#${c.id}`}>
            <summary className="flex cursor-pointer list-none items-center gap-4 p-5 [&::-webkit-details-marker]:hidden">
              <div className="min-w-0 flex-1">
                <p className="font-semibold">{c.label} <span className="ml-1 text-sm font-normal text-ink-3">{c.unit}</span></p>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {c.hazard_names.map((h) => <span key={h} className="rounded-md bg-surface-3 px-2 py-0.5 text-xs font-medium text-ink-2">{h}</span>)}
                </div>
              </div>
              <ChevronDown size={18} className="shrink-0 text-ink-3 transition-transform group-open:rotate-180" aria-hidden="true" />
            </summary>
            <dl className="m-0 grid gap-x-8 gap-y-5 border-t border-line p-5 md:grid-cols-2">
              {[
                ["Can it be measured in space?", c.measured_in_space],
                ["Why measure it", c.why],
                ["How spaceflight affects it", c.hazard_effect],
                ["When your flight surgeon needs to know", c.escalate],
                ["Prevention", c.prevention],
              ].map(([question, text]) => (
                <div key={question}>
                  <dt className="eyebrow">{question}</dt>
                  <dd className="m-0 mt-1.5 max-w-[65ch] text-sm text-ink-2">{text}</dd>
                </div>
              ))}
              <div>
                <dt className="eyebrow">Where the values in this app come from</dt>
                <dd className="m-0 mt-2 flex flex-wrap gap-x-4 gap-y-2">
                  {Object.entries(c.sources).map(([key, s]) => <span key={key} className="inline-flex items-center gap-1.5 text-sm">{key.replace(/_/g, " ")} <SourceBadge source={s} /></span>)}
                </dd>
              </div>
            </dl>
          </details>
        ))}
      </div>
    </div>
  );
}
