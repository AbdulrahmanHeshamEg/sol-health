import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { useIndicators } from "../api/hooks";
import { ErrorNote, Skeleton, SourceBadge } from "../components/ui";

export function Learn() {
  const cards = useIndicators();
  const { hash } = useLocation();
  useEffect(() => {
    if (cards.data && hash) document.getElementById(hash.slice(1))?.scrollIntoView({ block: "start" });
  }, [cards.data, hash]);
  if (cards.isError) return <ErrorNote error={cards.error} retry={() => cards.refetch()} />;
  if (!cards.data) return <Skeleton lines={8} height={26} />;
  return (
    <div>
      <h1 className="text-2xl">What we measure, and why</h1>
      <p className="mt-1 max-w-[70ch] text-base text-dust-dim">
        For each indicator: whether it can be measured in space, why it matters, how spaceflight changes it, when your flight surgeon needs to know, and how to prevent trouble.
      </p>
      <div className="mt-6 space-y-3">
        {cards.data.map((c) => (
          <details key={c.id} id={c.id} className="panel scroll-mt-4 p-5" open={hash === `#${c.id}`}>
            <summary className="cursor-pointer">
              <span className="display text-lg">{c.label}</span>
              <span className="ml-3 text-sm text-dust-dim">{c.unit}. Hazard: {c.hazard_names.join(", ").toLowerCase()}.</span>
            </summary>
            <dl className="mt-4 grid gap-x-8 gap-y-4 md:grid-cols-2">
              {[
                ["Can it be measured in space?", c.measured_in_space],
                ["Why measure it", c.why],
                ["How spaceflight affects it", c.hazard_effect],
                ["When your flight surgeon needs to know", c.escalate],
                ["Prevention", c.prevention],
              ].map(([q, text]) => (
                <div key={q}>
                  <dt className="text-sm text-dust-dim">{q}</dt>
                  <dd className="m-0 max-w-[60ch] text-base">{text}</dd>
                </div>
              ))}
              <div>
                <dt className="text-sm text-dust-dim">Where the values in this app come from</dt>
                <dd className="m-0 mt-1 flex flex-wrap gap-2">
                  {Object.entries(c.sources).map(([key, s]) => <span key={key} className="text-sm">{key.replace(/_/g, " ")} <SourceBadge source={s} /></span>)}
                </dd>
              </div>
            </dl>
          </details>
        ))}
      </div>
    </div>
  );
}
