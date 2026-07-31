export interface ComparableRow {
  match: string;
  ligne_aces_fr?: string;
  ligne_breaks_fr?: string;
  ligne_victoires_fr?: string;
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
  us_source?: string;
  us_source_label?: string;
  us_bookmaker?: string;
  prob_fair_fanduel?: string;
  ev_percent?: string;
  ev_percent_raw?: number | null;
  paire_fd_complete?: boolean;
  ecart_fr_moins_fd: string;
  meilleur_cote: string;
  compare_key?: string;
  fanduel_compare_key?: string;
  market_family?: string;
  player_name?: string;
  outcome?: string;
  captured_at?: string;
  fr_captured_at?: string;
  fd_captured_at?: string;
  us_captured_at?: string;
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
  skipped?: boolean;
  skip_reason?: string;
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
  markets?: string[];
  aces: MarketPayload;
  breaks: MarketPayload;
  victoires?: MarketPayload;
}

export type SportKey = "tennis" | "wnba" | "nba" | "baseball" | "soccer";
export type MarketKind = "aces" | "breaks" | "victoires" | "wnba" | "nba" | "baseball" | "soccer";
export type TennisMarketKind = "aces" | "breaks" | "victoires";

export type AcesPayload = MarketPayload;

export interface RunStatus {
  status: "idle" | "running" | "success" | "error" | "cancelled";
  message: string;
  sport?: SportKey;
  match_filter?: string;
  updated_at?: string;
  run_started_at?: string;
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
  market: TennisMarketKind,
): MarketPayload | null {
  if (!payload) {
    return null;
  }
  if (isCombinedPayload(payload)) {
    if (market === "aces") {
      return payload.aces;
    }
    if (market === "breaks") {
      return payload.breaks;
    }
    return payload.victoires ?? null;
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
    const sections = [payload.aces, payload.breaks, payload.victoires].filter(
      (section): section is MarketPayload => Boolean(section),
    );
    const comparable_count = sections.reduce((sum, section) => sum + (section.comparable_count ?? 0), 0);
    const fr_only_count = sections.reduce((sum, section) => sum + (section.fr_only_count ?? 0), 0);
    const primary = payload.aces ?? payload.breaks ?? payload.victoires;
    return {
      comparable_count,
      fr_only_count,
      partial: payload.partial ?? primary?.partial ?? true,
      matches_done: payload.matches_done ?? primary?.matches_done ?? 0,
      anchors_total: payload.anchors_total ?? primary?.anchors_total ?? 0,
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
      : marketKind === "victoires"
        ? "ligne_victoires_fr"
        : marketKind === "wnba" || marketKind === "nba" || marketKind === "baseball" || marketKind === "soccer"
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

export function formatFdContraire(row: ComparableRow): string {
  const us = row.cote_us_fanduel_contraire?.trim();
  const fr = row.cote_fr_fanduel_contraire?.trim();
  if (!us && !fr) {
    return "—";
  }
  const side = row.issue_fr_contraire?.trim();
  const prefix = side ? `${side} · ` : "";
  if (us && fr) {
    return `${prefix}${us} (${fr})`;
  }
  return `${prefix}${us || fr || "—"}`;
}

export function getTableColumns(marketKind: MarketKind) {
  const pariLabel =
    marketKind === "breaks"
      ? "Pari breaks"
      : marketKind === "victoires"
        ? "Pari victoire"
        : marketKind === "baseball"
          ? "Pari baseball"
          : marketKind === "soccer"
            ? "Prop foot"
            : marketKind === "wnba" || marketKind === "nba"
            ? "Prop joueur"
            : "Pari aces";
  const lineKey =
    marketKind === "breaks"
      ? "ligne_breaks"
      : marketKind === "victoires"
        ? "ligne_victoires"
        : marketKind === "wnba" || marketKind === "nba" || marketKind === "baseball" || marketKind === "soccer"
          ? "ligne_props"
          : "ligne_aces";

  const coreColumns = [
    { key: "match" as const, label: "Match", hint: "Joueur A vs joueur B" },
    {
      key: lineKey as "match",
      label: pariLabel,
      hint:
        marketKind === "victoires"
          ? "Vainqueur du match (moneyline)"
          : "Ligne comparee : seuil, joueur concerne, Plus ou Moins",
      format: (row: ComparableRow) => ligneLabel(row, marketKind),
    },
    {
      key: "marche_fanduel" as const,
      label: "Equiv. US",
      hint:
        marketKind === "wnba" || marketKind === "nba"
          ? "Meme prop joueur cote US (libelle anglais)"
          : marketKind === "baseball"
            ? "Meme marche baseball cote par la reference US"
            : marketKind === "soccer"
              ? "Meme prop foot cote US (buteur, decisif, tirs…)"
            : marketKind === "victoires"
              ? "Moneyline reference US"
              : "Meme marche cote US (libelle anglais)",
    },
    {
      key: "cote_fr" as const,
      label: "Cote FR",
      hint: "Meilleure cote decimale chez Unibet, Betclic ou Winamax",
    },
    { key: "bookmaker_fr" as const, label: "Book FR", hint: "Bookmaker FR retenu pour ce cote" },
    {
      key: "us_source_label" as const,
      label: "Book US",
      hint:
        marketKind === "baseball" || marketKind === "wnba" || marketKind === "nba" || marketKind === "soccer"
          ? "Source US reelle: FanDuel en priorite, sinon RotoWire · DraftKings"
          : "Source US reelle retenue sur la ligne",
    },
    {
      key: "cote_us_fanduel_ml" as const,
      label: "US (ML)",
      hint: "Cote moneyline de la reference US retenue pour ce cote",
    },
    {
      key: "cote_fr_fanduel" as const,
      label: "US (FR)",
      hint: "Cote de la reference US convertie en decimal FR",
    },
    {
      key: "cote_us_fanduel_contraire" as const,
      label: "US contraire",
      hint:
        marketKind === "victoires"
          ? "Cote US du joueur adverse"
          : "Cote US du cote oppose (ex. Moins si la ligne est Plus)",
      format: (row: ComparableRow) => formatFdContraire(row),
    },
    {
      key: "ecart_fr_moins_fd" as const,
      label: "Ecart",
      hint: "Cote FR moins cote US (FR). Positif = FR plus haut",
    },
    {
      key: "meilleur_cote" as const,
      label: "Qui paie mieux",
      hint: "Book FR ou reference US selon la cote la plus haute (brut)",
    },
  ];

  if (marketKind === "baseball" || marketKind === "soccer") {
    return coreColumns;
  }

  if (marketKind === "wnba" || marketKind === "nba") {
    return coreColumns;
  }

  return coreColumns.filter((column) => column.key !== "us_source_label");
}

export const TABLE_COLUMNS = getTableColumns("aces");

export type TableColumn = ReturnType<typeof getTableColumns>[number];
