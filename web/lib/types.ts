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

export const TABLE_COLUMNS: { key: keyof ComparableRow; label: string; hint: string }[] = [
  { key: "match", label: "Match", hint: "Joueur A vs joueur B" },
  {
    key: "issue_fr",
    label: "Plus / Moins",
    hint: "Sens de la ligne aces comparee (ex. Plus de 9,5 aces)",
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
