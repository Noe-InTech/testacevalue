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
  if (progress.comparable_count > 0 || progress.fr_only_count > 0) {
    return true;
  }
  if ((progress.matches_done ?? 0) > 0 || (progress.anchors_total ?? 0) > 0) {
    return true;
  }
  if (isCombinedPayload(payload)) {
    return Boolean(
      (payload.aces?.comparables?.length ?? 0) > 0 ||
        (payload.aces?.fr_only_comparables?.length ?? 0) > 0 ||
        (payload.aces?.match_progress?.length ?? 0) > 0 ||
        (payload.breaks?.comparables?.length ?? 0) > 0 ||
        (payload.breaks?.fr_only_comparables?.length ?? 0) > 0 ||
        (payload.breaks?.match_progress?.length ?? 0) > 0 ||
        (payload.victoires?.comparables?.length ?? 0) > 0 ||
        (payload.victoires?.fr_only_comparables?.length ?? 0) > 0 ||
        (payload.victoires?.match_progress?.length ?? 0) > 0,
    );
  }
  return Boolean(
    (payload.comparables?.length ?? 0) > 0 ||
      (payload.fr_only_comparables?.length ?? 0) > 0 ||
      (payload.match_progress?.length ?? 0) > 0,
  );
}

function slimTennisPayload(payload: ApiPayload): ApiPayload {
  if (isCombinedPayload(payload)) {
    return {
      ...payload,
      aces: {
        ...payload.aces,
        fd_only_comparables: [],
      },
      breaks: {
        ...payload.breaks,
        fd_only_comparables: [],
      },
      victoires: payload.victoires
        ? {
            ...payload.victoires,
            fd_only_comparables: [],
          }
        : payload.victoires,
    };
  }
  return {
    ...payload,
    fd_only_comparables: [],
  };
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
    try {
      window.localStorage.setItem(
        TENNIS_CACHE_KEY,
        JSON.stringify({ ...entry, payload: slimTennisPayload(payload) }),
      );
    } catch {
      // ignore quota errors
    }
  }
}

export function clearCachedTennisResults(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(TENNIS_CACHE_KEY);
}
