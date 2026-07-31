import type { ComparableRow, MarketPayload, RunStatus } from "@/lib/types";

export const SOCCER_CACHE_KEY = "soccer_last_results_v1";

export interface SoccerCachedResults {
  payload: MarketPayload;
  status: RunStatus | null;
  savedAt: string;
}

export interface SoccerStatFilter {
  id: string;
  label: string;
  families: string[];
}

export const SOCCER_STAT_FILTERS: SoccerStatFilter[] = [
  { id: "all", label: "Tous", families: [] },
  { id: "buteur", label: "Buteur", families: ["anytime_goalscorer"] },
  { id: "first", label: "1er buteur", families: ["first_goalscorer"] },
  { id: "decisif", label: "Décisif", families: ["score_or_assist"] },
  { id: "passeur", label: "Passeur", families: ["anytime_assist"] },
  { id: "tirs", label: "Tirs", families: ["shots_player"] },
  { id: "cadres", label: "Tirs cadrés", families: ["shots_on_target_player"] },
  { id: "carton", label: "Carton", families: ["player_card"] },
  { id: "corners", label: "Corners", families: ["corners_match"] },
];

export const SOCCER_BOOK_FILTERS = ["Tous", "Winamax", "Unibet", "Betclic"] as const;

export type SoccerBookFilter = (typeof SOCCER_BOOK_FILTERS)[number];

export function hasSoccerData(payload: MarketPayload | null | undefined): boolean {
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

export function loadCachedSoccerResults(): SoccerCachedResults | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(SOCCER_CACHE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as SoccerCachedResults;
    if (!parsed?.payload || !hasSoccerData(parsed.payload)) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function clearCachedSoccerResults(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(SOCCER_CACHE_KEY);
}

export function saveCachedSoccerResults(payload: MarketPayload, status: RunStatus | null): void {
  if (typeof window === "undefined" || !hasSoccerData(payload)) {
    return;
  }
  const entry: SoccerCachedResults = {
    payload,
    status,
    savedAt: new Date().toISOString(),
  };
  try {
    window.localStorage.setItem(SOCCER_CACHE_KEY, JSON.stringify(entry));
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
  const line = (row.ligne_props_fr || row.marche_fr || "").toLowerCase();
  if (line.includes("1er buteur") || line.includes("premier buteur")) {
    return "first_goalscorer";
  }
  if (line.includes("décisif") || line.includes("decisif")) {
    return "score_or_assist";
  }
  if (line.includes("passeur")) {
    return "anytime_assist";
  }
  if (line.includes("cadr")) {
    return "shots_on_target_player";
  }
  if (line.includes("tir")) {
    return "shots_player";
  }
  if (line.includes("carton")) {
    return "player_card";
  }
  if (line.includes("corner")) {
    return "corners_match";
  }
  if (line.includes("buteur")) {
    return "anytime_goalscorer";
  }
  return "";
}

export function filterSoccerRows(
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
  const stat = SOCCER_STAT_FILTERS.find((item) => item.id === statId) ?? SOCCER_STAT_FILTERS[0];
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
      row.player_name,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(needle);
  });
}

export function countRowsByStat(rows: ComparableRow[]): Record<string, number> {
  const counts: Record<string, number> = { all: rows.length };
  for (const filter of SOCCER_STAT_FILTERS) {
    if (filter.id === "all") {
      continue;
    }
    counts[filter.id] = rows.filter((row) => filter.families.includes(rowStatFamily(row))).length;
  }
  return counts;
}
