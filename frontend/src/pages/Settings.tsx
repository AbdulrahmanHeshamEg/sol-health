// Settings: the demo controls (which moment of the mission you see), your saved entries, and where the data comes from.
import { useState } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CalendarRange, Info, PlugZap, Trash2 } from "lucide-react";
import { api } from "../api/client";
import { useCrew, useDataMode, useMe, useMission } from "../api/hooks";
import { SolStrip } from "../components/SolStrip";
import { earthLink, lightTime } from "../components/EarthLink";
import { Card, ErrorNote, PageHeader, Skeleton, when } from "../components/ui";
import { useLinkWithAt } from "../state/replay";

export function Settings() {
  const me = useMe();
  const mission = useMission();
  const crew = useCrew();
  const mode = useDataMode();
  const link = useLinkWithAt();
  const queryClient = useQueryClient();
  const [cleared, setCleared] = useState<string | null>(null);

  async function clear() {
    if (!window.confirm("Delete every answer and eye photo you entered on this device? The demo data stays.")) return;
    try {
      await api.clearEntries();
      setCleared("Your entries were deleted.");
      await queryClient.invalidateQueries();
    } catch (err) {
      setCleared(err instanceof Error ? err.message : "Nothing was deleted.");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" />

      <Card title="Demo: which moment you see" icon={<CalendarRange size={18} />} aside="The app normally shows now">
        <p className="mb-5 max-w-[80ch] text-sm text-ink-2">
          The mission is simulated, so you can look at any moment of it. Pick a planted case or a sol; every page then shows what the app said at that moment,
          and a strip at the top reminds you that you are not looking at now.
        </p>
        {mission.isError ? <ErrorNote error={mission.error} retry={() => mission.refetch()} />
          : mission.data && crew.data ? <SolStrip mission={mission.data} crew={crew.data} /> : <Skeleton lines={3} height={14} />}
      </Card>

      <div className="grid items-start gap-6 lg:grid-cols-2">
        <Card title="Your entries" icon={<Trash2 size={18} />}>
          <p className="text-sm text-ink-2">Check-in answers and uploaded eye photos are kept on this device and replace the simulated values of that day.</p>
          <button className="btn-ghost mt-4" onClick={clear}><Trash2 size={14} />Delete my entries</button>
          {cleared && <p className="mt-2 text-sm" aria-live="polite">{cleared}</p>}
        </Card>

        <Card title="Connection" icon={<PlugZap size={18} />}>
          <p className="flex items-center gap-2 text-sm font-medium">
            <span className={`h-2.5 w-2.5 rounded-full ${mode === "live" ? "live-dot" : ""}`} style={{ background: mode === "live" ? "var(--color-ok)" : "var(--color-ink-3)" }} aria-hidden="true" />
            {mode === "live" ? "Connected to the engine" : "Offline snapshot"}
          </p>
          <p className="mt-1 text-sm text-ink-2">
            {mode === "live" ? "Check-ins, photos and every moment of the mission work." : "You can view the saved moments; check-ins and photos need the engine."}
          </p>
          {mission.data && <p className="mt-2 text-xs text-ink-3">Mission time runs from {when(mission.data.time_range.start)} to {when(mission.data.time_range.end)}. A message to Earth takes {lightTime(mission.data.earth_comm_delay_s)} ({earthLink(mission.data.earth_comm_delay_s).millionKm.toFixed(1)} million km), and a reply at least {earthLink(mission.data.earth_comm_delay_s).roundTrip}.</p>}
        </Card>
      </div>

      <Card title="About" icon={<Info size={18} />}>
        <p className="text-sm text-ink-2">{me.data ? `${me.data.name}, ${me.data.role}. ` : ""}Your flight surgeon is at {me.data?.flight_surgeon.where ?? "mission control"}.</p>
        <Link to={link("/about")} className="mt-3 inline-flex items-center gap-1 text-sm font-semibold no-underline">Data, sources and how the engine was checked <ArrowRight size={14} /></Link>
      </Card>
    </div>
  );
}
