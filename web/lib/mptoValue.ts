import type { ComparableRow, MarketKind } from "@/lib/types";

const KELLY_FRACTION = 0.25;

export interface MptoValueResult {
  edge: number;
  edgeLabel: string;
  kellyPercent: number;
  kellyLabel: string;
  fairOdds: number;
  mptoProbability: number;
}

export interface ValueBetRow {
  match: string;
  bet: string;
  opposite: string;
  coteFd: string;
  coteFr: string;
  bookmaker: string;
  edge: number;
  edgeLabel: string;
  kellyPercent: number;
  kellyLabel: string;
  compareKey?: string;
}

export function parseFrenchDecimal(value: string | undefined | null): number | null {
  if (!value?.trim()) {
    return null;
  }
  const normalized = value.trim().replace(/\s/g, "").replace(",", ".");
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed) || parsed <= 1) {
    return null;
  }
  return parsed;
}

/** MPTO de-vig sur un marche a 2 issues (cotes ref FanDuel). */
export function computeMptoValue(
  fdOdds: number,
  fdOppositeOdds: number,
  frOdds: number,
  kellyFraction = KELLY_FRACTION,
): MptoValueResult | null {
  if (fdOdds <= 1 || fdOppositeOdds <= 1 || frOdds <= 1) {
    return null;
  }

  const implicitProbabilities = [1 / fdOdds, 1 / fdOppositeOdds];
  const sumImplicit = implicitProbabilities[0] + implicitProbabilities[1];
  const margin = sumImplicit - 1;
  const mptoProbability = implicitProbabilities[0] - margin / 2;

  if (mptoProbability <= 0 || mptoProbability >= 1) {
    return null;
  }

  const fairOdds = 1 / mptoProbability;
  const edge = frOdds * mptoProbability - 1;
  const b = frOdds - 1;
  const q = 1 - mptoProbability;
  const kellyFull = b > 0 ? (b * mptoProbability - q) / b : -1;
  const kellyFractioned = kellyFull > 0 ? kellyFull * kellyFraction : 0;

  return {
    edge,
    edgeLabel: formatPercent(edge),
    kellyPercent: kellyFractioned * 100,
    kellyLabel: formatPercent(kellyFractioned, 2),
    fairOdds,
    mptoProbability,
  };
}

export function formatPercent(fraction: number, digits = 1): string {
  const value = fraction * 100;
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits).replace(".", ",")}%`;
}

export function formatBetLabel(row: ComparableRow, marketKind?: MarketKind): string {
  if (marketKind === "breaks" && row.ligne_breaks_fr) {
    return row.ligne_breaks_fr;
  }
  if ((marketKind === "wnba" || marketKind === "nba") && row.ligne_props_fr) {
    return row.ligne_props_fr;
  }
  if (marketKind === "aces" && row.ligne_aces_fr) {
    return row.ligne_aces_fr;
  }
  return row.ligne_props_fr || row.ligne_aces_fr || row.ligne_breaks_fr || row.marche_fr || row.issue_fr || "—";
}

export function computeValueFromComparable(
  row: ComparableRow,
  marketKind?: MarketKind,
): ValueBetRow | null {
  if (!row.paire_fd_complete) {
    return null;
  }

  const fdOdds = parseFrenchDecimal(row.cote_fr_fanduel);
  const fdOppositeOdds = parseFrenchDecimal(row.cote_fr_fanduel_contraire);
  const frOdds = parseFrenchDecimal(row.cote_fr);

  if (fdOdds === null || fdOppositeOdds === null || frOdds === null) {
    return null;
  }

  const mpto = computeMptoValue(fdOdds, fdOppositeOdds, frOdds);
  if (!mpto || mpto.edge <= 0) {
    return null;
  }

  return {
    match: row.match,
    bet: formatBetLabel(row, marketKind),
    opposite: row.issue_fr_contraire || "—",
    coteFd: row.cote_fr_fanduel,
    coteFr: row.cote_fr,
    bookmaker: row.bookmaker_fr,
    edge: mpto.edge,
    edgeLabel: mpto.edgeLabel,
    kellyPercent: mpto.kellyPercent,
    kellyLabel: mpto.kellyLabel,
    compareKey: row.compare_key,
  };
}

export function buildValueRows(
  rows: ComparableRow[],
  marketKind?: MarketKind,
): ValueBetRow[] {
  return rows
    .map((row) => computeValueFromComparable(row, marketKind))
    .filter((row): row is ValueBetRow => row !== null)
    .sort((left, right) => right.edge - left.edge);
}
