import type { ComparableRow, MarketPayload, RunStatus } from "@/lib/types";

export const BASEBALL_CACHE_KEY = "baseball_last_results_v1";

export interface BaseballCachedResults {
  payload: MarketPayload;
  status: RunStatus | null;
  savedAt: string;
}

export interface BaseballStatFilter {
  id: string;
  label: string;
  families: string[];
}

export const BASEBALL_STAT_FILTERS: BaseballStatFilter[] = [
  { id: "all", label: "Tous", families: [] },
  { id: "h2h", label: "Vainqueur", families: ["h2h"] },
  { id: "runs_total", label: "Total runs", families: ["runs_total"] },
  { id: "runs_team", label: "Total equipe", families: ["runs_team"] },
  { id: "f5_h2h", label: "F5 vainqueur", families: ["f5_h2h"] },
  { id: "f5_total", label: "F5 total runs", families: ["f5_runs_total"] },
  { id: "inning1_total", label: "1re manche total", families: ["inning1_runs_total"] },
  { id: "hr", label: "Home run", families: ["hr_player"] },
  { id: "runs_player", label: "Runs joueur", families: ["runs_player"] },
  { id: "hits", label: "Hits", families: ["hits_player"] },
  { id: "rbi", label: "RBI", families: ["rbi_player"] },
  { id: "total_bases", label: "Total bases", families: ["total_bases_player"] },
  { id: "sb", label: "Stolen bases", families: ["sb_player"] },
  { id: "strikeouts", label: "Strikeouts", families: ["strikeouts_pitcher"] },
];

export const BASEBALL_BOOK_FILTERS = ["Tous", "Winamax", "Unibet", "Betclic"] as const;
export type BaseballBookFilter = (typeof BASEBALL_BOOK_FILTERS)[number];

export function hasBaseballData(payload: MarketPayload | null | undefined): boolean {
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

export function loadCachedBaseballResults(): BaseballCachedResults | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(BASEBALL_CACHE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as BaseballCachedResults;
    if (!parsed?.payload || !hasBaseballData(parsed.payload)) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function clearCachedBaseballResults(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(BASEBALL_CACHE_KEY);
}

export function saveCachedBaseballResults(payload: MarketPayload, status: RunStatus | null): void {
  if (typeof window === "undefined" || !hasBaseballData(payload)) {
    return;
  }
  const entry: BaseballCachedResults = {
    payload,
    status,
    savedAt: new Date().toISOString(),
  };
  try {
    window.localStorage.setItem(BASEBALL_CACHE_KEY, JSON.stringify(entry));
  } catch {
    // ignore
  }
}

export function rowStatFamily(row: ComparableRow & { compare_key?: string; market_family?: string }): string {
  if (row.market_family) {
    return row.market_family;
  }
  if (row.compare_key) {
    return row.compare_key.split("|")[0] ?? "";
  }
  return "";
}

export function filterBaseballRows(
  rows: ComparableRow[],
  {
    statId,
    book,
    query,
    matchQuery,
  }: {
    statId: string;
    book: string;
    query: string;
    matchQuery: string;
  },
): ComparableRow[] {
  const stat = BASEBALL_STAT_FILTERS.find((item) => item.id === statId) ?? BASEBALL_STAT_FILTERS[0];
  const needle = query.trim().toLowerCase();
  const matchNeedle = matchQuery.trim().toLowerCase();

  return rows.filter((row) => {
    if (stat.families.length > 0) {
      const family = rowStatFamily(row);
      if (!stat.families.includes(family)) {
        return false;
      }
    }
    if (book !== "Tous" && row.bookmaker_fr && row.bookmaker_fr !== book) {
      return false;
    }
    if (matchNeedle && !row.match.toLowerCase().includes(matchNeedle)) {
      return false;
    }
    if (!needle) {
      return true;
    }
    const haystack = [
      row.match,
      row.bookmaker_fr,
      row.marche_fr,
      row.marche_fanduel,
      row.ligne_props_fr,
      row.issue_fr,
      row.meilleur_cote,
      (row as ComparableRow & { player_name?: string }).player_name,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(needle);
  });
}

export function countRowsByStat(rows: ComparableRow[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const filter of BASEBALL_STAT_FILTERS) {
    if (filter.id === "all") {
      continue;
    }
    counts[filter.id] = filterBaseballRows(rows, {
      statId: filter.id,
      book: "Tous",
      query: "",
      matchQuery: "",
    }).length;
  }
  return counts;
}
