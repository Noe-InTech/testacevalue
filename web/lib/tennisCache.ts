import type { ApiPayload, RunStatus } from "@/lib/types";
import { getPayloadProgressSnapshot, isCombinedPayload } from "@/lib/types";

export const TENNIS_CACHE_KEY = "tennis_last_results_v1";

export interface TennisCachedResults {
  payload: ApiPayload;
  status: RunStatus | null;
  savedAt: string;
}

export function hasTennisData(payload: ApiPayload | null | undefined): boolean {
  if (!payload) {
    return false;
  }
  const progress = getPayloadProgressSnapshot(payload);
  return progress.comparable_count > 0 || progress.fr_only_count > 0;
}

export function loadCachedTennisResults(): TennisCachedResults | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(TENNIS_CACHE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as TennisCachedResults;
    if (!parsed?.payload || !hasTennisData(parsed.payload)) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function saveCachedTennisResults(payload: ApiPayload, status: RunStatus | null): void {
  if (typeof window === "undefined" || !hasTennisData(payload)) {
    return;
  }
  const entry: TennisCachedResults = {
    payload,
    status,
    savedAt: new Date().toISOString(),
  };
  try {
    window.localStorage.setItem(TENNIS_CACHE_KEY, JSON.stringify(entry));
  } catch {
    // ignore
  }
}

export function clearCachedTennisResults(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(TENNIS_CACHE_KEY);
}
