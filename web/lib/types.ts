export interface ComparableRow {
  match: string;
  ligne_aces_fr?: string;
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
}

export interface MatchProgressRow {
  match: string;
  comparable_count: number;
  fr_only_count: number;
  fanduel_found: boolean;
}

export interface AcesPayload {
  source: string;
  generated_at: string;
  partial?: boolean;
  anchors_total?: number;
  matches_done?: number;
  comparable_count: number;
  fr_higher_count: number;
  value_count?: number;
  fr_only_count?: number;
  comparables: ComparableRow[];
  fr_higher_comparables: ComparableRow[];
  value_comparables?: ComparableRow[];
  fr_only_comparables?: ComparableRow[];
  match_progress?: MatchProgressRow[];
}

export interface RunStatus {
  status: "idle" | "running" | "success" | "error";
  message: string;
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

function ligneAcesLabel(row: ComparableRow): string {
  if (row.ligne_aces_fr?.trim()) {
    return row.ligne_aces_fr;
  }
  if (row.marche_fr?.trim() && row.issue_fr?.trim()) {
    return `${row.issue_fr} — ${row.marche_fr}`;
  }
  return row.marche_fr || row.issue_fr || "—";
}

export const TABLE_COLUMNS: {
  key: keyof ComparableRow | "ligne_aces";
  label: string;
  hint: string;
  format?: (row: ComparableRow) => string;
}[] = [
  { key: "match", label: "Match", hint: "Joueur A vs joueur B" },
  {
    key: "ligne_aces",
    label: "Pari aces",
    hint: "Ligne comparee : seuil, joueur concerne, Plus ou Moins",
    format: ligneAcesLabel,
  },
  {
    key: "marche_fanduel",
    label: "Equiv. FanDuel",
    hint: "Meme marche chez FanDuel (libelle anglais)",
  },
  {
    key: "cote_fr",
    label: "Cote FR",
    hint: "Meilleure cote decimale chez Unibet, Betclic ou Winamax",
  },
  { key: "bookmaker_fr", label: "Book FR", hint: "Bookmaker FR retenu pour ce cote" },
  {
    key: "cote_fr_contraire",
    label: "FR contraire",
    hint: "Cote FR du cote oppose (Under si Over, etc.)",
  },
  {
    key: "cote_us_fanduel_ml",
    label: "FD (US)",
    hint: "Cote FanDuel moneyline pour ce cote",
  },
  {
    key: "cote_us_fanduel_contraire",
    label: "FD contraire (US)",
    hint: "Cote FanDuel US du cote oppose — necessaire pour calculer la fair prob",
  },
  {
    key: "cote_fr_fanduel",
    label: "FD (FR)",
    hint: "Cote FanDuel convertie en decimal FR",
  },
  {
    key: "prob_fair_fanduel",
    label: "Prob. fair",
    hint: "Probabilite implicite sans vig, derivee de la paire Over/Under FanDuel",
  },
  {
    key: "ev_percent",
    label: "EV %",
    hint: "Expected value : prob. fair FanDuel x cote FR - 1",
  },
  {
    key: "ecart_fr_moins_fd",
    label: "Ecart",
    hint: "Cote FR moins cote FanDuel (FR). Positif = FR plus haut",
  },
  {
    key: "meilleur_cote",
    label: "Qui paie mieux",
    hint: "Book FR ou FanDuel selon la cote la plus haute (brut)",
  },
];
