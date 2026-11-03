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

  const payload = payloadFromPreloadedState(state);

  return NextResponse.json({
    ok: true,
    payload,
    html_bytes: html.length,
    match_count: Object.keys((payload.matches as Record<string, unknown>) || {}).length,
  });
}
