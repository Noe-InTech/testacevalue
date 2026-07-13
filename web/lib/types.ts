export interface ComparableRow {
  match: string;
  ligne_aces_fr?: string;
  ligne_breaks_fr?: string;
  ligne_props_fr?: string;
  issue_fr: string;
  issue_fr_contraire?: string;
  marche_fr: string;
  marche_fanduel: string;
  cote_fr: string;
  bookmaker_fr: string;
  cote_fr_contraire?: string;
  bookmaker_fr_contraire?: string;
  cote_us_fanduel_ml: string;
  cote_us_fanduel_contraire?: string;
  cote_fr_fanduel: string;
  cote_fr_fanduel_contraire?: string;
  prob_fair_fanduel?: string;
  ev_percent?: string;
  ev_percent_raw?: number | null;
  paire_fd_complete?: boolean;
  ecart_fr_moins_fd: string;
  meilleur_cote: string;
  compare_key?: string;
  market_family?: string;
  player_name?: string;
  outcome?: string;
  captured_at?: string;
  fr_captured_at?: string;
  fd_captured_at?: string;
}

export interface MatchProgressRow {
  match: string;
  comparable_count: number;
  fr_only_count: number;
  fd_only_count?: number;
  fr_ace_market_count?: number;
  fd_ace_market_count?: number;
  fr_market_count?: number;
  fd_market_count?: number;
  fanduel_found: boolean;
}

export interface MarketPayload {
  source: string;
  generated_at: string;
  partial?: boolean;
  anchors_total?: number;
  matches_done?: number;
  comparable_count: number;
  fr_higher_count: number;
  value_count?: number;
  fr_only_count?: number;
  fd_only_count?: number;
  fd_ace_event_count?: number;
  fr_ace_event_count?: number;
  fd_event_count?: number;
  fr_event_count?: number;
  comparables: ComparableRow[];
  fr_higher_comparables: ComparableRow[];
  value_comparables?: ComparableRow[];
  fr_only_comparables?: ComparableRow[];
  fd_only_comparables?: ComparableRow[];
  match_progress?: MatchProgressRow[];
  notes?: string[];
}

export interface CombinedPropsPayload {
  source: string;
  generated_at: string;
  partial?: boolean;
  anchors_total?: number;
  matches_done?: number;
  aces: MarketPayload;
  breaks: MarketPayload;
}

export type SportKey = "tennis" | "wnba";
export type MarketKind = "aces" | "breaks" | "wnba";

export type AcesPayload = MarketPayload;

export interface RunStatus {
  status: "idle" | "running" | "success" | "error";
  message: string;
  sport?: SportKey;
  match_filter?: string;
  updated_at?: string;
  generated_at?: string;
  anchors_total?: number;
  matches_done?: number;
  comparable_count?: number;
  fr_higher_count?: number;
  value_count?: number;
  fr_only_count?: number;
}

export type ApiPayload = MarketPayload | CombinedPropsPayload;

export function isCombinedPayload(payload: ApiPayload | null): payload is CombinedPropsPayload {
  return Boolean(payload && "aces" in payload && "breaks" in payload);
}

export function pickMarketPayload(
  payload: ApiPayload | null,
  market: "aces" | "breaks",
): MarketPayload | null {
  if (!payload) {
    return null;
  }
  if (isCombinedPayload(payload)) {
    return market === "aces" ? payload.aces : payload.breaks;
  }
  return market === "aces" ? payload : null;
}

export function getPayloadProgressSnapshot(payload: ApiPayload | null) {
  if (!payload) {
    return {
      comparable_count: 0,
      fr_only_count: 0,
      partial: true,
      matches_done: 0,
      anchors_total: 0,
    };
  }
  if (isCombinedPayload(payload)) {
    const aces = payload.aces;
    return {
      comparable_count: aces.comparable_count,
      fr_only_count: aces.fr_only_count ?? 0,
      partial: payload.partial ?? aces.partial ?? true,
      matches_done: payload.matches_done ?? aces.matches_done ?? 0,
      anchors_total: payload.anchors_total ?? aces.anchors_total ?? 0,
    };
  }
  return {
    comparable_count: payload.comparable_count,
    fr_only_count: payload.fr_only_count ?? 0,
    partial: payload.partial ?? true,
    matches_done: payload.matches_done ?? 0,
    anchors_total: payload.anchors_total ?? 0,
  };
}

function ligneLabel(row: ComparableRow, marketKind: MarketKind): string {
  const key =
    marketKind === "breaks"
      ? "ligne_breaks_fr"
      : marketKind === "wnba"
        ? "ligne_props_fr"
        : "ligne_aces_fr";
  const explicit = row[key]?.trim();
  if (explicit) {
    return explicit;
  }
  if (row.marche_fr?.trim() && row.issue_fr?.trim()) {
    return `${row.issue_fr} — ${row.marche_fr}`;
  }
  return row.marche_fr || row.issue_fr || "—";
}

export function getTableColumns(marketKind: MarketKind) {
  const pariLabel =
    marketKind === "breaks"
      ? "Pari breaks"
      : marketKind === "wnba"
        ? "Prop joueuse"
        : "Pari aces";
  const lineKey =
    marketKind === "breaks"
      ? "ligne_breaks"
      : marketKind === "wnba"
        ? "ligne_props"
        : "ligne_aces";

  const coreColumns = [
    { key: "match" as const, label: "Match", hint: "Joueur A vs joueur B" },
    {
      key: lineKey as "match",
      label: pariLabel,
      hint: "Ligne comparee : seuil, joueur concerne, Plus ou Moins",
      format: (row: ComparableRow) => ligneLabel(row, marketKind),
    },
    {
      key: "marche_fanduel" as const,
      label: "Equiv. FanDuel",
      hint:
        marketKind === "wnba"
          ? "Meme prop joueuse chez FanDuel (libelle anglais)"
          : "Meme marche chez FanDuel (libelle anglais)",
    },
    {
      key: "cote_fr" as const,
      label: "Cote FR",
      hint: "Meilleure cote decimale chez Unibet, Betclic ou Winamax",
    },
    { key: "bookmaker_fr" as const, label: "Book FR", hint: "Bookmaker FR retenu pour ce cote" },
    {
      key: "cote_us_fanduel_ml" as const,
      label: "FD (US)",
      hint: "Cote FanDuel moneyline pour ce cote",
    },
    {
      key: "cote_fr_fanduel" as const,
      label: "FD (FR)",
      hint: "Cote FanDuel convertie en decimal FR",
    },
    {
      key: "ecart_fr_moins_fd" as const,
      label: "Ecart",
      hint: "Cote FR moins cote FanDuel (FR). Positif = FR plus haut",
    },
    {
      key: "meilleur_cote" as const,
      label: "Qui paie mieux",
      hint: "Book FR ou FanDuel selon la cote la plus haute (brut)",
    },
  ];

  if (marketKind === "wnba") {
    return coreColumns;
  }

  return coreColumns;
}

export const TABLE_COLUMNS = getTableColumns("aces");

export type TableColumn = ReturnType<typeof getTableColumns>[number];
