export const WINAMAX_HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
  Referer: "https://www.winamax.fr/paris-sportifs",
  Origin: "https://www.winamax.fr",
};

export const PRELOADED_STATE_RE = /var PRELOADED_STATE = (\{[\s\S]*?\});\s*\n/;

export function parsePreloadedState(html: string): Record<string, unknown> | null {
  const match = PRELOADED_STATE_RE.exec(html);
  if (!match?.[1]) {
    return null;
  }
  try {
    const state = JSON.parse(match[1]) as unknown;
    return state && typeof state === "object" && !Array.isArray(state)
      ? (state as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

export function payloadFromPreloadedState(state: Record<string, unknown>): Record<string, unknown> {
  return {
    matches: state.matches ?? {},
    bets: state.bets ?? {},
    outcomes: state.outcomes ?? {},
    odds: state.odds ?? {},
    players: state.players ?? {},
    requestId: "vercel-preload",
    source: "html_preload",
  };
}
