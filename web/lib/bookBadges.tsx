import type { ReactNode } from "react";

export type FrBookKey = "winamax" | "unibet" | "betclic" | "";

export function frBookKey(bookmaker: string | undefined | null): FrBookKey {
  const text = String(bookmaker || "").trim().toLowerCase();
  if (!text) {
    return "";
  }
  if (text.includes("winamax")) {
    return "winamax";
  }
  if (text.includes("unibet")) {
    return "unibet";
  }
  if (text.includes("betclic")) {
    return "betclic";
  }
  return "";
}

export function frBookBadgeClass(bookmaker: string | undefined | null): string {
  const key = frBookKey(bookmaker);
  if (!key) {
    return "book-badge";
  }
  return `book-badge book-badge-${key}`;
}

export function FrBookBadge({
  bookmaker,
  fallback = "—",
}: {
  bookmaker?: string | null;
  fallback?: string;
}): ReactNode {
  const label = String(bookmaker || "").trim();
  if (!label) {
    return fallback;
  }
  return <span className={frBookBadgeClass(label)}>{label}</span>;
}

export function MatchLabel({
  match,
  isLive,
}: {
  match?: string | null;
  isLive?: boolean | null;
}): ReactNode {
  const label = String(match || "").trim() || "—";
  return (
    <span className="match-label">
      <span>{label}</span>
      {isLive ? <span className="live-badge">LIVE</span> : null}
    </span>
  );
}
