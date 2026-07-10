export interface ComparableRow {
  match: string;
  ligne_aces_fr?: string;
  issue_fr: string;
  marche_fr: string;
  marche_fanduel: string;
  cote_fr: string;
  bookmaker_fr: string;
  cote_us_fanduel_ml: string;
  cote_fr_fanduel: string;
  ecart_fr_moins_fd: string;
  meilleur_cote: string;
}

export interface AcesPayload {
  source: string;
  generated_at: string;
  partial?: boolean;
  comparable_count: number;
  fr_higher_count: number;
  fr_only_count?: number;
  comparables: ComparableRow[];
  fr_higher_comparables: ComparableRow[];
  fr_only_comparables?: ComparableRow[];
}

export interface RunStatus {
  status: "idle" | "running" | "success" | "error";
  message: string;
  match_filter?: string;
  updated_at?: string;
  generated_at?: string;
  comparable_count?: number;
  fr_higher_count?: number;
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
  { key: "bookmaker_fr", label: "Bookmaker", hint: "Bookmaker FR retenu pour cette ligne" },
  {
    key: "cote_us_fanduel_ml",
    label: "FanDuel (US)",
    hint: "Cote FanDuel au format americain (moneyline)",
  },
  {
    key: "cote_fr_fanduel",
    label: "FanDuel (FR)",
    hint: "Meme cote FanDuel convertie en decimal FR (2 decimales)",
  },
  {
    key: "ecart_fr_moins_fd",
    label: "Ecart",
    hint: "Cote FR moins cote FanDuel (FR). Positif = FR plus haut",
  },
  {
    key: "meilleur_cote",
    label: "Qui paie mieux",
    hint: "Book FR ou FanDuel selon la cote la plus haute",
  },
];