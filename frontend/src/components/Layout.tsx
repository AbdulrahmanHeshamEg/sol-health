import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import {
  BookOpen, Check, ChevronDown, ClipboardCheck, Clock3, HeartPulse, History, Home, Menu, Moon, Settings,
  Stethoscope, Sun, Wind, X,
} from "lucide-react";
import { useAssessment, useDataMode, useMe, useMission, useMockMarks } from "../api/hooks";
import type { ReplayMark } from "../api/types";
import { useCheckIn } from "../state/checkin";
import { toMs, useLinkWithAt, useReplay } from "../state/replay";
import { AstronautArt, LogoMark, MarsGlobe } from "./art";
import { CheckInWizard } from "./CheckInWizard";
import { EarthLink } from "./EarthLink";
import { Avatar, StatusBadge, clock, when } from "./ui";

const NAV = [
  { to: "/", label: "Today", icon: Home },
  { to: "/body", label: "My body", icon: HeartPulse },
  { to: "/cabin", label: "Cabin", icon: Wind },
  { to: "/doctor", label: "Flight surgeon", icon: Stethoscope },
  { to: "/learn", label: "Learn", icon: BookOpen },
  { to: "/settings", label: "Settings", icon: Settings },
] as const;

/** "Sol-1 (fictional Mars surface mission)" → ["Sol-1", "Fictional Mars surface mission"] */
function splitMissionName(name: string): [string, string | null] {
  const m = name.match(/^(.*?)\s*\((.*)\)\s*$/);
  return m ? [m[1], m[2].charAt(0).toUpperCase() + m[2].slice(1)] : [name, null];
}

function useTheme() {
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    const set = document.documentElement.dataset.theme;
    if (set === "light" || set === "dark") return set;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });
  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("sol-theme", next); } catch { /* storage blocked: the choice lasts this visit */ }
    setTheme(next);
  };
  return { theme, toggle };
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const link = useLinkWithAt();
  const me = useMe();
  const mission = useMission();
  const now = useAssessment(me.data?.astronaut_id ?? "");
  const mode = useDataMode();
  const m = mission.data;
  const sol = now.data?.mission_day ?? m?.current_day ?? 0;      // the sol of the moment on screen
  const progress = m ? Math.min(100, (sol / m.planned_duration_days) * 100) : 0;

  return (
    <div className="flex h-full flex-col gap-6 overflow-y-auto px-4 py-5">
      <Link to={link("/")} onClick={onNavigate} className="flex items-center gap-3 px-2 text-ink no-underline">
        <LogoMark size={40} />
        <span className="leading-tight">
          <span className="block text-[1.15rem] font-bold tracking-tight">Sol Health</span>
          <span className="block text-xs text-ink-3">Your onboard medical copilot</span>
        </span>
      </Link>
      <nav aria-label="Sections" className="flex flex-col gap-1">
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={link(to)} end={to === "/"} onClick={onNavigate}
            className={({ isActive }) => `flex items-center gap-3 rounded-xl px-3 py-2.5 text-[0.93rem] font-medium no-underline transition-colors ${isActive ? "bg-brand-soft text-brand-ink" : "text-ink-2 hover:bg-surface-2 hover:text-ink"}`}>
            <Icon size={19} aria-hidden="true" />{label}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto space-y-4 rounded-2xl border border-line bg-surface-2 p-4">
        <div className="flex flex-col items-center border-b border-line pb-4 text-center [@media(max-height:820px)]:hidden">
          <AstronautArt width={128} />
          <p className="mt-1 text-sm font-semibold">Healthy astronaut,<br />successful mission.</p>
        </div>
        {me.data && (
          <div className="flex items-center gap-3">
            <Avatar name={me.data.name} size={36} />
            <div className="min-w-0 leading-tight">
              <p className="truncate text-sm font-semibold">{me.data.name}</p>
              <p className="truncate text-xs text-ink-3">{me.data.role}</p>
            </div>
          </div>
        )}
        {m ? (
          <>
            <div>
              <p className="text-xs text-ink-3"><span className="tnum font-semibold text-ink">Sol {sol}</span> of {m.planned_duration_days}</p>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-3"><div className="h-full rounded-full bg-brand" style={{ width: `${progress}%` }} /></div>
            </div>
            <EarthLink seconds={m.earth_comm_delay_s} />
          </>
        ) : <div className="skeleton h-14" />}
        <div className="flex items-center gap-2.5 border-t border-line pt-3 text-sm"
          title={mode === "live" ? "Your readings are up to date" : "No connection. Showing the last saved readings."}>
          <span className={`h-2.5 w-2.5 rounded-full ${mode === "live" ? "live-dot" : ""}`} style={{ background: mode === "live" ? "var(--color-ok)" : "var(--color-ink-3)" }} aria-hidden="true" />
          <span className="font-medium">{mode === "live" ? "Up to date" : "Offline, last saved data"}</span>
        </div>
      </div>
    </div>
  );
}

/** Demo replay: jump to a marked moment, or back to now. The sol-by-sol scrubber is in Settings. */
function ReplayMenu() {
  const { at, isDefault, go: goTo } = useReplay();
  const mission = useMission();
  const mode = useDataMode();
  const mockMarks = useMockMarks();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [open]);
  const marks: ReplayMark[] = mode === "mock" ? (mockMarks.data ?? []) : (mission.data?.replay_marks ?? []);
  const go = (target: string | null) => { goTo(target); setOpen(false); };

  return (
    <div ref={box} className="relative">
      <button className="btn-ghost" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)} title="Demo: look at another moment">
        <History size={15} aria-hidden="true" />
        <span className="hidden md:inline">{isDefault ? "Demo" : at ? when(at) : "Latest"}</span>
        <ChevronDown size={14} aria-hidden="true" />
      </button>
      {open && (
        <div role="menu" className="absolute right-0 z-30 mt-2 w-72 rounded-2xl border border-line bg-surface p-2 shadow-[var(--shadow-pop)]">
          <p className="eyebrow px-3 pb-1 pt-2">Demo · jump to a moment</p>
          {marks.map((mk) => ({ id: mk.id, label: mk.label, target: (mk.show_at ?? mk.at).replace(" ", "T") })).map((item, i, all) => {
            // two moments can share a time (the typical day is also a planted case): tick only the first
            const active = at !== null && all.findIndex((x) => toMs(x.target) === toMs(at)) === i;
            return (
              <button key={item.id} role="menuitemradio" aria-checked={active} onClick={() => go(item.target)}
                className="flex w-full items-center gap-3 rounded-xl border-0 bg-transparent px-3 py-2 text-left text-sm hover:bg-surface-2">
                <span className="w-4 shrink-0 text-brand">{active && <Check size={16} aria-hidden="true" />}</span>
                <span className="flex-1">
                  <span className="block font-medium">{item.label}</span>
                  <span className="block text-xs text-ink-3">{when(item.target)}{item.id === "typical_day" ? " · opens by default" : ""}</span>
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function TopBar({ onMenu }: { onMenu: () => void }) {
  const mission = useMission();
  const me = useMe();
  const now = useAssessment(me.data?.astronaut_id ?? "");
  const checkin = useCheckIn();
  const { theme, toggle } = useTheme();
  const { at } = useReplay();
  const m = mission.data;
  const [name, setting] = m ? splitMissionName(m.name) : ["", null];

  return (
    <header className="sticky top-0 z-20 border-b border-line bg-[color-mix(in_srgb,var(--color-canvas)_85%,transparent)] backdrop-blur">
      <div className="flex h-16 items-center gap-2 px-4 sm:gap-3 sm:px-6 lg:px-8">
        <button className="icon-btn lg:hidden" onClick={onMenu} aria-label="Open navigation"><Menu size={18} /></button>
        <div className="flex min-w-0 items-center gap-3">
          <span className="hidden sm:block"><MarsGlobe size={34} /></span>
          <div className="min-w-0 leading-tight">
            <p className="truncate font-semibold">{m ? name : "Loading mission"}</p>
            <p className="truncate text-xs text-ink-3">{m ? `${setting ?? m.vehicle} · Sol ${now.data?.mission_day ?? m.current_day}` : " "}</p>
          </div>
          {now.data && <span className="hidden md:inline-flex"><StatusBadge level={now.data.status} size="sm" /></span>}
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button className="btn px-3 sm:px-4" onClick={checkin.show}><ClipboardCheck size={16} aria-hidden="true" /><span className="hidden sm:inline">Check in</span><span className="sr-only sm:hidden">Daily check-in</span></button>
          <ReplayMenu />
          {m && (
            <span className="hidden items-center gap-1.5 rounded-[9px] border border-line-strong bg-surface px-3 py-[0.42rem] text-[0.85rem] font-medium xl:inline-flex" title="Habitat time (UTC)">
              <Clock3 size={15} className="text-ink-3" aria-hidden="true" /><span className="tnum">{clock(at ?? m.now)}</span><span className="text-ink-3">UTC</span>
            </span>
          )}
          <button className="icon-btn" onClick={toggle} aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}>
            {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
          </button>
        </div>
      </div>
    </header>
  );
}

export function Layout() {
  const mission = useMission();
  const me = useMe();
  const mode = useDataMode();
  const checkin = useCheckIn();
  const { setBounds } = useReplay();
  const queryClient = useQueryClient();
  const [drawer, setDrawer] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => { queryClient.invalidateQueries(); }, [mode, queryClient]);     // engine came back, or went away: reload everything
  const range = mission.data?.time_range;
  useEffect(() => { if (range) setBounds(range); }, [range?.start, range?.end]);   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { setDrawer(false); window.scrollTo(0, 0); }, [pathname]);

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[256px_minmax(0,1fr)]">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-2 focus:z-50 focus:rounded-lg focus:bg-surface focus:p-2">Skip to content</a>
      <aside className="sticky top-0 hidden h-screen border-r border-line bg-surface lg:block"><Sidebar /></aside>
      {drawer && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-black/40" onClick={() => setDrawer(false)} />
          <aside className="absolute inset-y-0 left-0 w-[280px] max-w-[85vw] bg-surface shadow-[var(--shadow-pop)]">
            <button className="icon-btn absolute right-3 top-4 z-10" onClick={() => setDrawer(false)} aria-label="Close navigation"><X size={18} /></button>
            <Sidebar onNavigate={() => setDrawer(false)} />
          </aside>
        </div>
      )}
      <div className="flex min-w-0 flex-col">
        <TopBar onMenu={() => setDrawer(true)} />
        <main id="main" className="mx-auto w-full max-w-[1320px] flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8"><Outlet /></main>
        <footer className="mx-auto w-full max-w-[1320px] px-4 pb-8 text-xs text-ink-3 sm:px-6 lg:px-8">
          <p className="max-w-[90ch] border-t border-line pt-4">
            Decision support, not a medical device. You are a fictional, simulated astronaut; the statistics come from real data
            (PMData, NASA OSDR EDA, NASA/JPL MSL RAD), and every value is marked real, simulated or entered by you.
            Your flight surgeon makes all medical decisions.
          </p>
        </footer>
      </div>
      {checkin.open && me.data && <CheckInWizard astronautId={me.data.astronaut_id} onClose={checkin.hide} />}
    </div>
  );
}
