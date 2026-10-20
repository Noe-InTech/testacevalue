import type { ComparableRow } from "@/lib/types";

export const FR_BOOK_ORDER = ["Winamax", "Unibet", "Betclic"] as const;

export type FrBookOddsEntry = {
  key: string;
  label: string;
  odds: number;
  oddsFormatted: string;
  isBest: boolean;
};

export type ByBookPayload = {
  odds?: number;
  bookmaker?: string;
  bookmaker_label?: string;
};

function formatFrenchOdds(value: number): string {
  return value.toFixed(2).replace(".", ",");
}

export function readByBook(row: ComparableRow): Record<string, ByBookPayload> {
  const raw = (row as ComparableRow & { by_book?: Record<string, ByBookPayload> }).by_book;
  return raw && typeof raw === "object" ? raw : {};
}

/** Cotes des 3 books FR sur la même ligne comparable (meilleur mis en avant). */
export function listFrBookOdds(row: ComparableRow): FrBookOddsEntry[] {
  const byBook = readByBook(row);
  const bestLabel = (row.bookmaker_fr || "").trim();
  const entries: FrBookOddsEntry[] = [];

  for (const [key, payload] of Object.entries(byBook)) {
    if (!payload || typeof payload !== "object") {
      continue;
    }
    const odds = Number(payload.odds);
    if (!Number.isFinite(odds)) {
      continue;
    }
    const label = String(payload.bookmaker_label || key).trim();
    entries.push({
      key,
      label,
      odds,
      oddsFormatted: formatFrenchOdds(odds),
      isBest: Boolean(bestLabel && label === bestLabel),
    });
  }

  entries.sort((a, b) => {
    const ai = FR_BOOK_ORDER.indexOf(a.label as (typeof FR_BOOK_ORDER)[number]);
    const bi = FR_BOOK_ORDER.indexOf(b.label as (typeof FR_BOOK_ORDER)[number]);
    const aRank = ai >= 0 ? ai : 99;
    const bRank = bi >= 0 ? bi : 99;
    if (aRank !== bRank) {
      return aRank - bRank;
    }
    return a.label.localeCompare(b.label, "fr");
  });

  if (entries.length === 0 && row.cote_fr && bestLabel) {
    const odds = Number(String(row.cote_fr).replace(",", "."));
    if (Number.isFinite(odds)) {
      entries.push({
        key: bestLabel.toLowerCase(),
        label: bestLabel,
        odds,
        oddsFormatted: row.cote_fr,
        isBest: true,
      });
    }
  }

  return entries;
}

export function rowHasFrBookLabel(row: ComparableRow, book: string): boolean {
  if (listFrBookOdds(row).some((entry) => entry.label === book)) {
    return true;
  }
  const present = row.fr_books_present;
  if (Array.isArray(present) && present.includes(book)) {
    return true;
  }
  return row.bookmaker_fr === book;
}
