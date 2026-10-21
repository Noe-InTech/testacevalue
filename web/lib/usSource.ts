/** Badge du book US affiché dans les tableaux (FanDuel, RotoWire ou Pinnacle). */
export function usSourceBadgeClass(source?: string): string {
  if (source === "pinnacle") {
    return "us-source-badge us-source-badge-pinnacle";
  }
  if (source === "rotowire") {
    return "us-source-badge us-source-badge-rotowire";
  }
  return "us-source-badge us-source-badge-fanduel";
}

export function usSourceBadgeLabel(row: {
  us_source?: string;
  us_source_label?: string;
  us_bookmaker?: string;
}): string {
  if (row.us_source === "rotowire" && row.us_bookmaker) {
    return `${row.us_source_label || "RotoWire"} · ${row.us_bookmaker}`;
  }
  return row.us_source_label || "FanDuel";
}
