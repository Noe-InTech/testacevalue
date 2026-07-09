export interface ComparableRow {
  match: string;
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
  comparable_count: number;
  fr_higher_count: number;
  comparables: ComparableRow[];
  fr_higher_comparables: ComparableRow[];
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

export const TABLE_COLUMNS: { key: keyof ComparableRow; label: string }[] = [
  { key: "match", label: "Match" },
  { key: "issue_fr", label: "Issue" },
  { key: "cote_fr", label: "Cote FR" },
  { key: "bookmaker_fr", label: "Book FR" },
  { key: "cote_us_fanduel_ml", label: "ML US" },
  { key: "cote_fr_fanduel", label: "Cote FD" },
  { key: "ecart_fr_moins_fd", label: "Ecart" },
  { key: "meilleur_cote", label: "Meilleur" },
];
