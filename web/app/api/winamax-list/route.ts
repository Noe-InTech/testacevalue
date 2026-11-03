import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

const WINAMAX_HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
  Referer: "https://www.winamax.fr/paris-sportifs",
  Origin: "https://www.winamax.fr",
};

const PRELOADED_STATE_RE = /var PRELOADED_STATE = (\{[\s\S]*?\});\s*\n/;

function extractRunnerSecret(request: Request): string {
  return (
    request.headers.get("X-Runner-Secret")?.trim() ||
    request.headers.get("x-runner-secret")?.trim() ||
    new URL(request.url).searchParams.get("secret")?.trim() ||
    ""
  );
}

function authorized(secret: string): boolean {
  const expected = process.env.RUNNER_SECRET?.trim();
  return Boolean(expected && secret === expected);
}

function parsePreloadedState(html: string): Record<string, unknown> | null {
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

export async function GET(request: Request) {
  if (!authorized(extractRunnerSecret(request))) {
    return NextResponse.json({ ok: false, error: "Secret runner incorrect." }, { status: 401 });
  }

  const sport = new URL(request.url).searchParams.get("sport")?.trim() || "2";
  const pageUrl = `https://www.winamax.fr/paris-sportifs/sports/${encodeURIComponent(sport)}`;

  let html: string;
  try {
    const response = await fetch(pageUrl, {
      cache: "no-store",
      headers: WINAMAX_HEADERS,
    });
    if (!response.ok) {
      return NextResponse.json(
        { ok: false, error: `Winamax HTTP ${response.status}` },
        { status: 502 },
      );
    }
    html = await response.text();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json({ ok: false, error: message }, { status: 502 });
  }

  const state = parsePreloadedState(html);
  if (!state || (!("sports" in state) && !("matches" in state))) {
    return NextResponse.json(
      {
        ok: false,
        error: "PRELOADED_STATE sans calendrier — egress Vercel aussi filtré ?",
        html_bytes: html.length,
      },
      { status: 502 },
    );
  }

  const payload: Record<string, unknown> = {
    matches: state.matches ?? {},
    bets: state.bets ?? {},
    outcomes: state.outcomes ?? {},
    odds: state.odds ?? {},
    requestId: "vercel-preload",
    source: "html_preload",
  };

  return NextResponse.json({
    ok: true,
    payload,
    html_bytes: html.length,
    match_count: Object.keys((payload.matches as Record<string, unknown>) || {}).length,
  });
}
