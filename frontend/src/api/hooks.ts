// TanStack Query hooks. `at` is part of every query key, so moving the replay slider refetches everything.
import { keepPreviousData, useQueries, useQuery } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";
import { api, getDataMode, mockMarks, onDataMode } from "./client";
import { useReplay } from "../state/replay";

const STATIC = { staleTime: Infinity };
const timed = { placeholderData: keepPreviousData, staleTime: 60_000 };

export const useDataMode = () => useSyncExternalStore(onDataMode, getDataMode);

export const useMeta = () => useQuery({ queryKey: ["meta"], queryFn: api.meta, ...STATIC });
export const useIndicators = () => useQuery({ queryKey: ["indicators"], queryFn: api.indicators, ...STATIC });
export const useCases = () => useQuery({ queryKey: ["cases"], queryFn: api.cases, ...STATIC });
export const useMockMarks = () => useQuery({ queryKey: ["mock-marks"], queryFn: mockMarks, ...STATIC });
export const useProfile = (id: string) => useQuery({ queryKey: ["profile", id], queryFn: () => api.profile(id), ...STATIC });
/** The astronaut this app belongs to. */
export const useMe = () => useQuery({ queryKey: ["me"], queryFn: api.me, ...STATIC });

export function useMission() {
  const { at } = useReplay();
  return useQuery({ queryKey: ["mission", at], queryFn: () => api.mission(at), ...timed });
}
export function useCrew() {
  const { at } = useReplay();
  return useQuery({ queryKey: ["crew", at], queryFn: () => api.crew(at), ...timed });
}
export function useAssessment(id: string) {
  const { at } = useReplay();
  return useQuery({ queryKey: ["assessment", id, at], queryFn: () => api.assessment(id, at), ...timed });
}
export function useAssessments(ids: string[]) {
  const { at } = useReplay();
  return useQueries({ queries: ids.map((id) => ({ queryKey: ["assessment", id, at], queryFn: () => api.assessment(id, at), ...timed })) });
}
export function useVitals(id: string) {
  const { at } = useReplay();
  return useQuery({ queryKey: ["vitals", id, at], queryFn: () => api.vitals(id, at), ...timed });
}
export function useDaily(id: string) {
  const { at } = useReplay();
  return useQuery({ queryKey: ["daily", id, at], queryFn: () => api.daily(id, at), ...timed });
}
export function useTimeline(id: string) {
  const { at } = useReplay();
  return useQuery({ queryKey: ["timeline", id, at], queryFn: () => api.timeline(id, at), ...timed });
}
export function useForecast(id: string) {
  const { at } = useReplay();
  return useQuery({ queryKey: ["forecast", id, at], queryFn: () => api.forecast(id, at), ...timed });
}
export function useRadiation(id: string | undefined) {
  const { at } = useReplay();
  return useQuery({ queryKey: ["radiation", id, at], queryFn: () => api.radiation(id!, at), enabled: !!id, ...timed });
}
export function useReports(id: string | undefined) {
  const { at } = useReplay();
  return useQuery({ queryKey: ["reports", id, at], queryFn: () => api.reports(id!, at), enabled: !!id, ...timed });
}
export function useQuestions(id: string | undefined) {
  const { at } = useReplay();
  return useQuery({ queryKey: ["questions", id, at], queryFn: () => api.questions(id!, at), enabled: !!id, ...timed });
}
export function useBrief(id: string | undefined) {
  const { at } = useReplay();
  return useQuery({ queryKey: ["brief", id, at], queryFn: () => api.brief(id!, at), enabled: !!id, ...timed });
}
export function useEyeExams(id: string | undefined) {
  const { at } = useReplay();
  return useQuery({ queryKey: ["eye-exams", id, at], queryFn: () => api.eyeExams(id!, at), enabled: !!id, ...timed });
}
export function useReminders(id: string) {
  const { at } = useReplay();
  return useQuery({ queryKey: ["reminders", id, at], queryFn: () => api.reminders(id, at), ...timed });
}
/** Whole-mission hourly status: the data behind the sol strip. Not tied to `at`. */
export function useMissionTimelines(ids: string[]) {
  return useQueries({ queries: ids.map((id) => ({ queryKey: ["timeline-all", id], queryFn: () => api.timelineAll(id), ...STATIC })) });
}
