// Settings: the demo controls (which moment of the mission you see), your saved entries, and where the data comes from.
import { useState } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useCrew, useDataMode, useMe, useMission } from "../api/hooks";
import { SolStrip } from "../components/SolStrip";
import { ErrorNote, Panel, Skeleton, when } from "../components/ui";
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
      <h1 className="text-2xl">Settings</h1>

      <Panel title="Demo: which moment you see" aside="The app normally shows now">
        <p className="mb-4 max-w-[72ch] text-base text-dust-dim">
          The mission is simulated, so you can look at any moment of it. Pick a planted case or a sol; every page then shows what the app said at that moment.
          A strip at the top of each page reminds you that you are not looking at now.
        </p>
        {mission.isError ? <ErrorNote error={mission.error} retry={() => mission.refetch()} />
          : mission.data && crew.data ? <SolStrip mission={mission.data} crew={crew.data} /> : <Skeleton lines={3} height={14} />}
      </Panel>

      <Panel title="Your entries">
        <p className="max-w-[72ch] text-base">Answers to the daily questions and uploaded eye photos are kept on this device and replace the simulated values of that day.</p>
        <button className="btn-quiet mt-3" onClick={clear}>Delete my entries</button>
        {cleared && <p className="mt-2 text-sm" aria-live="polite">{cleared}</p>}
      </Panel>

      <Panel title="Connection">
        <p className="text-base">
          {mode === "live" ? "Connected to the engine: answers, photos and every moment of the mission work." : "Offline snapshot: you can view the saved moments, but answers and photos need the engine."}
        </p>
        {mission.data && <p className="mt-1 text-sm text-dust-dim">Mission time runs from {when(mission.data.time_range.start)} to {when(mission.data.time_range.end)}. A message to Earth takes about {Math.round(mission.data.earth_comm_delay_s / 60)} minutes.</p>}
      </Panel>

      <Panel title="About">
        <p className="text-base">{me.data ? `${me.data.name}, ${me.data.role}.` : ""} Your flight surgeon is at {me.data?.flight_surgeon.where ?? "mission control"}.</p>
        <p className="mt-2 text-base"><Link to={link("/about")}>Data, sources and how the engine was checked</Link></p>
      </Panel>
    </div>
  );
}
