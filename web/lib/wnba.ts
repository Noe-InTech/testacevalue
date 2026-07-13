import type { ComparableRow, MarketPayload, RunStatus } from "@/lib/types";

export const WNBA_CACHE_KEY = "wnba_last_results_v1";

export interface WnbaCachedResults {
  payload: MarketPayload;
  status: RunStatus | null;
  savedAt: string;
}

export interface WnbaStatFilter {
  id: string;
  label: string;
  families: string[];
}

export const WNBA_STAT_FILTERS: WnbaStatFilter[] = [
  { id: "all", label: "Tous", families: [] },
  { id: "points", label: "Points", families: ["points_player"] },
  { id: "rebounds", label: "Rebonds", families: ["rebounds_player"] },
  { id: "assists", label: "Passes", families: ["assists_player"] },
  { id: "threes", label: "3 pts", families: ["threes_made_player"] },
  { id: "blocks", label: "Contres", families: ["blocks_player"] },
  { id: "steals", label: "Interceptions", families: ["steals_player"] },
  { id: "turnovers", label: "Pertes", families: ["turnovers_player"] },
  { id: "pts_reb", label: "Pts+Reb", families: ["points_rebounds_player"] },
  { id: "pts_ast", label: "Pts+Ast", families: ["points_assists_player"] },
  { id: "reb_ast", label: "Reb+Ast", families: ["rebounds_assists_player"] },
  { id: "pra", label: "PRA", families: ["pra_player"] },
  { id: "double_double", label: "Double-double", families: ["double_double_player"] },
];

export const WNBA_BOOK_FILTERS = ["Tous", "Winamax", "Unibet", "Betclic"] as const;

export type WnbaBookFilter = (typeof WNBA_BOOK_FILTERS)[number];

export function hasWnbaData(payload: MarketPayload | null | undefined): boolean {
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

export function loadCachedWnbaResults(): WnbaCachedResults | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(WNBA_CACHE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as WnbaCachedResults;
    if (!parsed?.payload || !hasWnbaData(parsed.payload)) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function clearCachedWnbaResults(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(WNBA_CACHE_KEY);
}

export function saveCachedWnbaResults(payload: MarketPayload, status: RunStatus | null): void {
  if (typeof window === "undefined" || !hasWnbaData(payload)) {
    return;
  }
  const entry: WnbaCachedResults = {
    payload,
    status,
    savedAt: new Date().toISOString(),
  };
  try {
    window.localStorage.setItem(WNBA_CACHE_KEY, JSON.stringify(entry));
  } catch {
    // localStorage plein ou desactive — ignorer
  }
}

export function rowStatFamily(row: ComparableRow & { compare_key?: string; market_family?: string }): string {
  if (row.market_family) {
    return row.market_family;
  }
  if (row.compare_key) {
    return row.compare_key.split("|")[0] ?? "";
  }
  const line = (row.ligne_props_fr || row.marche_fr || "").toLowerCase();
  if (line.includes("rebond")) {
    return "rebounds_player";
  }
  if (line.includes("3 point") || line.includes("3pts")) {
    return "threes_made_player";
  }
  if (line.includes("double-double")) {
    return "double_double_player";
  }
  if (line.includes("pts+reb+ast") || line.includes("pra")) {
    return "pra_player";
  }
  if (line.includes("pts+reb")) {
    return "points_rebounds_player";
  }
  if (line.includes("pts+ast")) {
    return "points_assists_player";
  }
  if (line.includes("reb+ast")) {
    return "rebounds_assists_player";
  }
  if (line.includes("passe")) {
    return "assists_player";
  }
  if (line.includes("point")) {
    return "points_player";
  }
  return "";
}

export function filterWnbaRows(
  rows: ComparableRow[],
  {
    statId,
    book,
    query,
    matchQuery,
  }: {
    statId: string;
    book: WnbaBookFilter;
    query: string;
    matchQuery: string;
  },
): ComparableRow[] {
  const stat = WNBA_STAT_FILTERS.find((item) => item.id === statId) ?? WNBA_STAT_FILTERS[0];
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
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(needle);
  });
}

export function countRowsByStat(rows: ComparableRow[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const filter of WNBA_STAT_FILTERS) {
    if (filter.id === "all") {
      continue;
    }
    counts[filter.id] = filterWnbaRows(rows, {
      statId: filter.id,
      book: "Tous",
      query: "",
      matchQuery: "",
    }).length;
  }
  return counts;
}
