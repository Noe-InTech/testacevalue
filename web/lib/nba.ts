import type { MarketPayload, RunStatus } from "@/lib/types";

import {
  WNBA_BOOK_FILTERS,
  WNBA_STAT_FILTERS,
  filterWnbaRows,
  countRowsByStat,
  rowStatFamily,
  type WnbaBookFilter,
} from "@/lib/wnba";

export const NBA_CACHE_KEY = "nba_last_results_v1";

export interface NbaCachedResults {
  payload: MarketPayload;
  status: RunStatus | null;
  savedAt: string;
}

export const NBA_BOOK_FILTERS = WNBA_BOOK_FILTERS;
export const NBA_STAT_FILTERS = WNBA_STAT_FILTERS;
export type NbaBookFilter = WnbaBookFilter;

export function hasNbaData(payload: MarketPayload | null | undefined): boolean {
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

export function loadCachedNbaResults(): NbaCachedResults | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(NBA_CACHE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as NbaCachedResults;
    if (!parsed?.payload || !hasNbaData(parsed.payload)) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function clearCachedNbaResults(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(NBA_CACHE_KEY);
}

export function saveCachedNbaResults(payload: MarketPayload, status: RunStatus | null): void {
  if (typeof window === "undefined" || !hasNbaData(payload)) {
    return;
  }
  const entry: NbaCachedResults = {
    payload,
    status,
    savedAt: new Date().toISOString(),
  };
  try {
    window.localStorage.setItem(NBA_CACHE_KEY, JSON.stringify(entry));
  } catch {
    // ignore
  }
}

export { filterWnbaRows as filterNbaRows, countRowsByStat, rowStatFamily };
