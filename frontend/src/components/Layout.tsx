import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { NavLink, Outlet } from "react-router-dom";
import { useCrew, useDataMode, useMission } from "../api/hooks";
import { useLinkWithAt, useReplay } from "../state/replay";
import { SolStrip } from "./SolStrip";
import { ErrorNote, Skeleton } from "./ui";

const NAV = [["/", "Me"], ["/cabin", "Cabin"], ["/reports", "Flight surgeon"], ["/learn", "What we measure"], ["/about", "Data and sources"]] as const;

export function Layout() {
  const mission = useMission();
  const crew = useCrew();
  const mode = useDataMode();
  const link = useLinkWithAt();
  const { setBounds } = useReplay();
  const queryClient = useQueryClient();
  useEffect(() => { queryClient.invalidateQueries(); }, [mode, queryClient]);     // engine came back, or went away: reload everything
  const range = mission.data?.time_range;
  useEffect(() => { if (range) setBounds(range); }, [range?.start, range?.end]);   // eslint-disable-line react-hooks/exhaustive-deps

  const m = mission.data;
  const delayMin = m ? Math.round(m.earth_comm_delay_s / 60) : null;

  return (
    <div className="mx-auto flex min-h-screen max-w-[1320px] flex-col px-5 pb-8 lg:px-8">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-2 focus:z-10 focus:bg-hab focus:p-2">Skip to content</a>
      <header className="pt-5">
        <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-2">
          <div>
            <p className="display text-2xl">Sol Health</p>
            <p className="text-sm text-dust-dim">
              {m ? `${m.name}. Sol ${m.current_day} of ${m.planned_duration_days}. A message to Earth takes about ${delayMin} minutes each way, so you act first and your flight surgeon is kept informed.` : "Loading the mission"}
            </p>
          </div>
          <p className="text-sm" title={mode === "live" ? "Answers come from the engine running in the API" : "The API is not reachable. Showing saved engine answers."}>
            <span aria-hidden="true" style={{ display: "inline-block", width: 9, height: 9, borderRadius: 99, marginRight: 7, background: mode === "live" ? "var(--color-dusk)" : "var(--color-dust-dim)" }} />
            {mode === "live" ? "Engine connected" : "Offline snapshot"}
          </p>
        </div>
        <div className="panel mt-4 p-4">
          {mission.isError ? <ErrorNote error={mission.error} retry={() => mission.refetch()} />
            : m && crew.data ? <SolStrip mission={m} crew={crew.data} />
            : crew.isError ? <ErrorNote error={crew.error} retry={() => crew.refetch()} />
            : <Skeleton lines={3} height={12} />}
        </div>
        <nav className="mt-4 flex flex-wrap gap-x-6 gap-y-1 border-b border-line" aria-label="Sections">
          {NAV.map(([to, label]) => (
            <NavLink key={to} to={link(to)} end={to === "/"}
              className={({ isActive }) => `display -mb-px border-b-[3px] pb-2 text-base no-underline ${isActive ? "border-dusk text-dust" : "border-transparent text-dust-dim hover:text-dust"}`}>
              {label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main id="main" className="flex-1 py-6"><Outlet /></main>
      <footer className="border-t border-line pt-4 text-sm text-dust-dim">
        <p className="max-w-[78ch]">
          Decision support, not a medical device. The astronaut is fictional and simulated; the statistics come from real data
          (PMData, NASA OSDR EDA, NASA/JPL MSL RAD), and every value is marked real or simulated.
          Your flight surgeon makes all medical decisions.
        </p>
      </footer>
    </div>
  );
}
