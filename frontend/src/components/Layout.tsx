import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, NavLink, Outlet } from "react-router-dom";
import { useAssessment, useDataMode, useMe, useMission } from "../api/hooks";
import { useLinkWithAt, useReplay } from "../state/replay";
import { StatusChip, when } from "./ui";

const NAV = [["/", "Today"], ["/body", "My body"], ["/eyes", "Eye exam"], ["/cabin", "Cabin"], ["/doctor", "My doctor"],
  ["/learn", "Learn"], ["/settings", "Settings"]] as const;

/** Shown on every page while you look at an earlier moment of the demo mission. */
function DemoStrip() {
  const { at, setAt, setPlaying } = useReplay();
  const link = useLinkWithAt();
  if (!at) return null;
  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-sm px-4 py-2 text-sm" style={{ background: "var(--color-dusk-deep)" }} role="status">
      <span>Demo: you are looking at <span className="font-bold">{when(at)}</span>, not now.</span>
      <button className="btn-quiet py-1 text-sm" onClick={() => { setPlaying(false); setAt(null); }}>Back to now</button>
      <Link to={link("/settings")}>Change in Settings</Link>
    </div>
  );
}

export function Layout() {
  const me = useMe();
  const mission = useMission();
  const now = useAssessment(me.data?.astronaut_id ?? "");
  const mode = useDataMode();
  const link = useLinkWithAt();
  const { setBounds } = useReplay();
  const queryClient = useQueryClient();
  useEffect(() => { queryClient.invalidateQueries(); }, [mode, queryClient]);     // engine came back, or went away: reload everything
  const range = mission.data?.time_range;
  useEffect(() => { if (range) setBounds(range); }, [range?.start, range?.end]);   // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="mx-auto flex min-h-screen max-w-[1240px] flex-col px-5 pb-8 lg:px-8">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-2 focus:z-10 focus:bg-hab focus:p-2">Skip to content</a>
      <header className="pt-5">
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
          <Link to={link("/")} className="display text-2xl text-dust no-underline">Sol Health</Link>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-sm">
            {now.data && <StatusChip level={now.data.status} />}
            {mission.data && <span className="text-dust-dim">Sol {now.data?.mission_day ?? mission.data.current_day} · Earth {Math.round(mission.data.earth_comm_delay_s / 60)} min away</span>}
            <span title={mode === "live" ? "Answers come from the engine running in the API" : "The engine is not reachable. Showing saved answers."}>
              <span aria-hidden="true" style={{ display: "inline-block", width: 8, height: 8, borderRadius: 99, marginRight: 6, background: mode === "live" ? "var(--color-dusk)" : "var(--color-dust-dim)" }} />
              {mode === "live" ? "Engine on" : "Offline"}
            </span>
          </div>
        </div>
        <nav className="mt-4 flex flex-wrap gap-x-6 gap-y-1 border-b border-line" aria-label="Sections">
          {NAV.map(([to, label]) => (
            <NavLink key={to} to={link(to)} end={to === "/"}
              className={({ isActive }) => `display -mb-px border-b-[3px] pb-2 text-base no-underline ${isActive ? "border-dusk text-dust" : "border-transparent text-dust-dim hover:text-dust"}`}>
              {label}
            </NavLink>
          ))}
        </nav>
        <DemoStrip />
      </header>
      <main id="main" className="flex-1 py-6"><Outlet /></main>
      <footer className="border-t border-line pt-4 text-sm text-dust-dim">
        <p className="max-w-[78ch]">
          Decision support, not a medical device. You are a fictional, simulated astronaut; the statistics come from real data
          (PMData, NASA OSDR EDA, NASA/JPL MSL RAD), and every value is marked real, simulated or entered by you.
          Your flight surgeon makes all medical decisions.
        </p>
      </footer>
    </div>
  );
}
