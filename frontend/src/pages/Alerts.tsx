import { Link } from "react-router-dom";
import { useAssessments, useCrew } from "../api/hooks";
import type { Alert, Level } from "../api/types";
import { ErrorNote, LEVEL_COLOR, Skeleton, StatusChip } from "../components/ui";
import { useLinkWithAt } from "../state/replay";

const RANK: Record<Level, number> = { RED: 0, YELLOW: 1, GREEN: 2 };

export function Alerts() {
  const crew = useCrew();
  const ids = (crew.data ?? []).map((c) => c.astronaut_id);
  const results = useAssessments(ids);
  const link = useLinkWithAt();
  if (crew.isError) return <ErrorNote error={crew.error} retry={() => crew.refetch()} />;
  if (!crew.data || results.some((r) => r.isLoading)) return <Skeleton lines={6} height={30} />;
  const failed = results.find((r) => r.isError);
  if (failed) return <ErrorNote error={failed.error} retry={() => results.forEach((r) => r.refetch())} />;

  const rows: Array<{ alert: Alert; id: string; name: string }> = [];
  results.forEach((r, i) => r.data?.alerts.forEach((alert) => rows.push({ alert, id: ids[i], name: crew.data![i].name })));
  rows.sort((a, b) => RANK[a.alert.level] - RANK[b.alert.level]);
  // The same cabin or radiation alert reaches every crewmember: show it once with everyone it affects.
  const grouped = new Map<string, { alert: Alert; people: Array<{ id: string; name: string }> }>();
  for (const r of rows) {
    const shared = r.alert.kind === "spe" || (r.alert.kind === "hard_limit" && r.alert.signal === "cabin_co2_mmhg");
    const key = shared ? `${r.alert.kind}|${r.alert.message}` : `${r.id}|${r.alert.kind}|${r.alert.message}`;
    const g = grouped.get(key) ?? { alert: r.alert, people: [] };
    g.people.push({ id: r.id, name: r.name });
    grouped.set(key, g);
  }
  const list = [...grouped.values()];

  return (
    <div>
      <h1 className="text-2xl">Alerts across the crew</h1>
      <p className="mt-1 text-sm text-dust-dim">{list.length ? "Most urgent first. Each one says what moved, how far and for how long." : ""}</p>
      {list.length === 0 ? (
        <p className="mt-6 max-w-[60ch] text-lg">No alerts at this moment. Use the sol strip above to look at another day.</p>
      ) : (
        <ul className="m-0 mt-5 list-none space-y-3 p-0">
          {list.map(({ alert, people }, i) => (
            <li key={i} className="panel p-5" style={{ borderLeft: `6px solid ${LEVEL_COLOR[alert.level]}` }}>
              <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                <StatusChip level={alert.level} />
                <h2 className="text-lg">{alert.message}</h2>
              </div>
              <p className="mt-1 max-w-[72ch] text-base">{alert.reason}</p>
              <p className="mt-2 text-sm text-dust-dim">
                {people.length > 1 ? "Affects " : ""}
                {people.map((p, k) => <span key={p.id}>{k > 0 && ", "}<Link to={link(`/crew/${p.id}`)}>{p.name}</Link></span>)}
                {`. ${alert.source === "rule" ? "Clinical limit" : `Statistical model: ${alert.model}`}. Hazard: ${alert.hazard.toLowerCase()}.`}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
