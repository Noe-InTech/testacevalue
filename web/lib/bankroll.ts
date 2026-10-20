"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

export const BANKROLL_STORAGE_KEY = "aces_bankroll_eur";

export function loadBankrollInput(): string {
  if (typeof window === "undefined") {
    return "";
  }
  return window.localStorage.getItem(BANKROLL_STORAGE_KEY) ?? "";
}

export function saveBankrollInput(raw: string): void {
  if (typeof window === "undefined") {
    return;
  }
  const trimmed = raw.trim();
  if (!trimmed) {
    window.localStorage.removeItem(BANKROLL_STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(BANKROLL_STORAGE_KEY, trimmed);
}

/** Parse saisie FR (espaces, virgule décimale). */
export function parseBankrollInput(raw: string): number | null {
  const normalized = raw.trim().replace(/\s/g, "").replace(",", ".");
  if (!normalized) {
    return null;
  }
  const value = Number(normalized);
  if (!Number.isFinite(value) || value <= 0) {
    return null;
  }
  return value;
}

/** `kellyPercent` est en points (ex. 2,5 pour 2,5 % de bankroll). */
export function stakeFromKellyPercent(bankrollEur: number, kellyPercent: number): number {
  return (bankrollEur * kellyPercent) / 100;
}

export function formatEuroStake(amount: number): string {
  return `${amount.toFixed(2).replace(".", ",")} €`;
}

export function formatKellyWithStake(
  kellyLabel: string,
  kellyPercent: number,
  bankrollEur: number | null,
): string {
  if (bankrollEur === null) {
    return kellyLabel;
  }
  const stake = stakeFromKellyPercent(bankrollEur, kellyPercent);
  return `${kellyLabel} (${formatEuroStake(stake)})`;
}

export function useBankroll() {
  const [input, setInputState] = useState("");

  useEffect(() => {
    setInputState(loadBankrollInput());
  }, []);

  const setInput = useCallback((next: string) => {
    setInputState(next);
    saveBankrollInput(next);
  }, []);

  const bankrollEur = useMemo(() => parseBankrollInput(input), [input]);
  const inputInvalid = Boolean(input.trim()) && bankrollEur === null;

  return { input, setInput, bankrollEur, inputInvalid };
}
