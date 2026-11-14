// One function per endpoint. Every read takes an optional `at` timestamp (mission replay).
// Mock mode: when VITE_USE_MOCK=true, or when the API cannot be reached, responses come from /mock/*.json
// (copies of data/demo/api_snapshots). The snapshots hold the current moment and a few replay marks.
import type {
  Assessment, Brief, CrewCard, DailyRow, EyeExam, Forecast, IndicatorCard, Me, Meta, Mission, PlantedCase, Profile, Questions,
  Radiation, Reminders, ReplayMark, Report, TelemetryRow, TimelinePoint,
} from "./types";

const FORCE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
const BASE = import.meta.env.VITE_API_BASE ?? "";

export type DataMode = "live" | "mock";
let mode: DataMode = FORCE_MOCK ? "mock" : "live";
const listeners = new Set<(m: DataMode) => void>();
export const getDataMode = () => mode;
export function onDataMode(fn: (m: DataMode) => void) {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}
function setMode(next: DataMode) {
  if (next !== mode) { mode = next; listeners.forEach((fn) => fn(next)); }
}

/** While on snapshots (and not forced there), look for the API again; switch back as soon as it answers. */
if (!FORCE_MOCK && typeof window !== "undefined") {
  window.setInterval(async () => {
    if (mode !== "mock") return;
    try {
      const res = await fetch(BASE + "/api/health", { signal: AbortSignal.timeout(3000) });
      if (res.ok) setMode("live");
    } catch { /* still offline */ }
  }, 10_000);
}

export class NotInSnapshot extends Error {
  constructor() { super("This moment is not in the offline snapshot. Pick one of the marked moments, or start the API."); }
}

let marksPromise: Promise<ReplayMark[]> | null = null;
export function mockMarks(): Promise<ReplayMark[]> {
  marksPromise ??= fetch("/mock/replay_marks.json").then((r) => (r.ok ? r.json() : []));
  return marksPromise;
}

const norm = (s: string) => s.replace(" ", "T").slice(0, 19);
const sameMoment = (a: string, b: string) => norm(a) === norm(b);

async function fromMock<T>(file: string, at?: string | null, timed = true): Promise<T> {
  let path = `/mock/${file}.json`;
  if (at && timed) {
    const mark = (await mockMarks()).find((m) => sameMoment(m.at, at));
    if (!mark) throw new NotInSnapshot();
    path = `/mock/at/${mark.id}/${file}.json`;
  }
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Snapshot ${file} is missing. Run "python -m sol_ml.snapshots" in ml/ and rebuild.`);
  return res.json();
}

async function get<T>(url: string, mockFile: string, at?: string | null, timed = true): Promise<T> {
  if (mode === "live") {
    let res: Response | null = null;
    try {
      const u = new URL(BASE + url, window.location.origin);
      if (at) u.searchParams.set("at", at);
      res = await fetch(u, { signal: AbortSignal.timeout(30_000) });
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") throw err;     // the page moved on; the API is fine
      setMode("mock");               // the API cannot be reached: fall back to the saved snapshots
    }
    if (res) {
      if (res.ok) return res.json();
      if (res.status < 500) {
        const body = await res.json().catch(() => null);
        throw new Error(typeof body?.detail === "string" ? body.detail : `Request failed (${res.status})`);
      }
      setMode("mock");               // the dev proxy answers 5xx when the API is down
    }
  }
  return fromMock<T>(mockFile, at, timed);
}

/** Photos are served by the API; offline they come from the saved snapshot. */
export const photoUrl = (url: string) => (mode === "mock" ? url.replace("/api/eye-photos/", "/mock/eye-photos/") : BASE + url);

async function send<T>(url: string, method: "POST" | "DELETE", body?: unknown): Promise<T> {
  if (mode === "mock") throw new Error("This needs the engine running: start the API (uvicorn api.main:app --port 8000) and try again.");
  const res = await fetch(BASE + url, {
    method, headers: body ? { "Content-Type": "application/json" } : undefined, body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => null))?.detail;
    throw new Error(Array.isArray(detail) ? detail.map((d: { msg: string }) => d.msg).join("; ") : detail ?? `Not saved (${res.status}).`);
  }
  return res.json();
}

export const api = {
  mission: (at?: string | null) => get<Mission>("/api/mission", "mission", at),
  meta: () => get<Meta>("/api/meta", "meta", null, false),
  indicators: () => get<IndicatorCard[]>("/api/indicators", "indicators", null, false),
  cases: () => get<PlantedCase[]>("/api/demo/cases", "cases", null, false),
  crew: (at?: string | null) => get<CrewCard[]>("/api/crew", "crew", at),
  me: () => get<Me>("/api/me", "me", null, false),
  reports: (id: string, at?: string | null) => get<Report[]>(`/api/crew/${id}/reports`, `${id}_reports`, at),
  questions: (id: string, at?: string | null) => get<Questions>(`/api/crew/${id}/questions`, `${id}_questions`, at),
  brief: (id: string, at?: string | null) => get<Brief>(`/api/crew/${id}/daily-brief`, `${id}_brief`, at),
  eyeExams: (id: string, at?: string | null) => get<EyeExam[]>(`/api/crew/${id}/eye-exams`, `${id}_eye_exams`, at),

  /** Save answers to today's questions. They change your assessment, so they need the engine (the live API). */
  answer: (id: string, values: Record<string, number>, at?: string | null) =>
    send<Assessment>(`/api/crew/${id}/answers`, "POST", { values, at: at ?? undefined }),
  /** Upload an eye photo (any image); the engine measures it against your baseline photo. */
  eyePhoto: (id: string, imageBase64: string, filename: string, at?: string | null) =>
    send<{ exam: EyeExam; assessment: Assessment }>(`/api/crew/${id}/eye-photo`, "POST", { image_base64: imageBase64, filename, at: at ?? undefined }),
  /** Forget every answer and photo you entered (the demo data stays). */
  clearEntries: () => send<{ cleared: boolean }>("/api/me/entries", "DELETE"),
  profile: (id: string) => get<Profile>(`/api/crew/${id}`, `${id}_profile`, null, false),
  assessment: (id: string, at?: string | null) => get<Assessment>(`/api/crew/${id}/assessment`, `${id}_assessment`, at),
  vitals: (id: string, at?: string | null) => get<TelemetryRow[]>(`/api/crew/${id}/vitals?hours=72`, `${id}_vitals_72h`, at),
  daily: (id: string, at?: string | null) => get<DailyRow[]>(`/api/crew/${id}/daily?days=30`, `${id}_daily_30d`, at),
  timeline: (id: string, at?: string | null) => get<TimelinePoint[]>(`/api/crew/${id}/timeline?hours=72`, `${id}_timeline_72h`, at),
  timelineAll: (id: string) => get<TimelinePoint[]>(`/api/crew/${id}/timeline?hours=1800`, `${id}_timeline_all`, null, false),
  forecast: (id: string, at?: string | null) => get<Forecast>(`/api/crew/${id}/forecast?horizon_days=90`, `${id}_forecast`, at),
  radiation: (id: string, at?: string | null) => get<Radiation>(`/api/crew/${id}/radiation`, `${id}_radiation`, at),
  reminders: (id: string, at?: string | null) => get<Reminders>(`/api/crew/${id}/reminders`, `${id}_reminders`, at),

};
