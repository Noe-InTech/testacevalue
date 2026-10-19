import { NextResponse } from "next/server";

import { requestBetclicShare, runnerEnabled } from "@/lib/runner";

export async function POST(request: Request) {
  if (!runnerEnabled()) {
    return NextResponse.json(
      { error: "Runner EU non configuré (RUNNER_URL / RUNNER_SECRET)." },
      { status: 503 },
    );
  }

  let body: {
    selection_id?: string;
    match_id?: string;
    market_id?: string;
    match_url?: string;
  };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Corps JSON invalide." }, { status: 400 });
  }

  const selectionId = String(body.selection_id || "").trim();
  const matchId = String(body.match_id || "").trim();
  const marketId = String(body.market_id || "").trim();
  const matchUrl = String(body.match_url || "").trim();
  if (!selectionId || !matchId || !marketId) {
    return NextResponse.json(
      { error: "selection_id, match_id et market_id sont requis." },
      { status: 400 },
    );
  }

  const response = await requestBetclicShare({
    selectionId,
    matchId,
    marketId,
    matchUrl,
  });
  const data = await response.json().catch(() => ({}));
  return NextResponse.json(data, { status: response.status });
}
