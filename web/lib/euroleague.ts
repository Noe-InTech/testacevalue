import type { MarketPayload, RunStatus } from "@/lib/types";

import {
  WNBA_BOOK_FILTERS,
  WNBA_STAT_FILTERS,
  filterWnbaRows,
  countRowsByStat,
  rowStatFamily,
  type WnbaBookFilter,
  type WnbaStatFilter,
} from "@/lib/wnba";

export const EUROLEAGUE_CACHE_KEY = "euroleague_last_results_v1";

export interface EuroleagueCachedResults {
  payload: MarketPayload;
  status: RunStatus | null;
  savedAt: string;
}

const EUROLEAGUE_STAT_IDS = ["all", "points", "rebounds", "assists", "threes"] as const;

export const EUROLEAGUE_STAT_FILTERS: WnbaStatFilter[] = WNBA_STAT_FILTERS.filter((item) =>
  (EUROLEAGUE_STAT_IDS as readonly string[]).includes(item.id),
);

export const EUROLEAGUE_BOOK_FILTERS = WNBA_BOOK_FILTERS;
export type EuroleagueBookFilter = WnbaBookFilter;

export function hasEuroleagueData(payload: MarketPayload | null | undefined): boolean {
  if (!payload) {
    return false;
  }
  return (
    (payload.comparable_count ?? 0) > 0 ||
    (payload.fr_only_count ?? 0) > 0 ||
    (payload.fd_only_count ?? 0) > 0 ||
    (payload.comparables?.length ?? 0) > 0
  );
}

export function loadCachedEuroleagueResults(): EuroleagueCachedResults | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(EUROLEAGUE_CACHE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as EuroleagueCachedResults;
    if (!parsed?.payload || !hasEuroleagueData(parsed.payload)) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function clearCachedEuroleagueResults(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(EUROLEAGUE_CACHE_KEY);
}

export function saveCachedEuroleagueResults(payload: MarketPayload, status: RunStatus | null): void {
  if (typeof window === "undefined" || !hasEuroleagueData(payload)) {
    return;
  }
  const entry: EuroleagueCachedResults = {
    payload,
    status,
    savedAt: new Date().toISOString(),
  };
  try {
    window.localStorage.setItem(EUROLEAGUE_CACHE_KEY, JSON.stringify(entry));
  } catch {
    // ignore
  }
}

export { filterWnbaRows as filterEuroleagueRows, countRowsByStat, rowStatFamily };
