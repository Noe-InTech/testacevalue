import { NextResponse } from "next/server";

import {
  WINAMAX_HEADERS,
  parsePreloadedState,
  payloadFromPreloadedState,
} from "@/lib/winamaxPreload";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

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

export async function GET(request: Request) {
  if (!authorized(extractRunnerSecret(request))) {
    return NextResponse.json({ ok: false, error: "Secret runner incorrect." }, { status: 401 });
  }

  const matchId = new URL(request.url).searchParams.get("matchId")?.trim();
  if (!matchId || !/^\d+$/.test(matchId)) {
    return NextResponse.json({ ok: false, error: "Parametre matchId requis." }, { status: 400 });
  }

  const pageUrl = `https://www.winamax.fr/paris-sportifs/match/${encodeURIComponent(matchId)}`;

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
  if (!state || !("bets" in state)) {
    return NextResponse.json(
      {
        ok: false,
        error: "PRELOADED_STATE sans marches — page match filtree ?",
        html_bytes: html.length,
      },
      { status: 502 },
    );
  }

  const payload = payloadFromPreloadedState(state);
  const bets = (payload.bets as Record<string, unknown>) || {};

  return NextResponse.json({
    ok: true,
    payload,
    html_bytes: html.length,
    bet_count: Object.keys(bets).length,
  });
}
