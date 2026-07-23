import { NextResponse } from "next/server";

import { isAuthorized, triggerWorkflow } from "@/lib/github";
import { runnerEnabled, triggerRunner } from "@/lib/runner";

export async function POST(request: Request) {
  let body: { secret?: string; match?: string; sport?: string; markets?: string | string[] };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Corps JSON invalide." }, { status: 400 });
  }

  if (!isAuthorized(body.secret)) {
    return NextResponse.json({ error: "Code secret incorrect." }, { status: 401 });
  }

  const match = (body.match || "").trim();
  const sport = (body.sport || "tennis").trim().toLowerCase();
  const markets = Array.isArray(body.markets)
    ? body.markets.map((item) => String(item).trim()).filter(Boolean).join(",")
    : (body.markets || "").trim();
  const response = runnerEnabled()
    ? await triggerRunner(match, sport, markets)
    : await triggerWorkflow(match, "live");
  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}
