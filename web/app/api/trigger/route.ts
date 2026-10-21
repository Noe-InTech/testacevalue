import { NextResponse } from "next/server";

import { isAuthorized, triggerWorkflow } from "@/lib/github";
import { runnerEnabled, triggerRunner } from "@/lib/runner";

export async function POST(request: Request) {
  let body: {
    secret?: string;
    match?: string;
    sport?: string;
    markets?: string | string[];
    nba_hours?: number;
    hours?: number;
    use_rotowire?: boolean;
    rotowire?: boolean;
    use_pinnacle?: boolean;
    pinnacle?: boolean;
  };
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
  if (sport === "soccer") {
    return NextResponse.json(
      {
        error:
          "Foot temporairement désactivé (scrape trop lourd pour la VM). Utilise tennis / baseball / WNBA / NBA.",
        disabled: true,
        sport: "soccer",
      },
      { status: 503 },
    );
  }
  const markets = Array.isArray(body.markets)
    ? body.markets.map((item) => String(item).trim()).filter(Boolean).join(",")
    : (body.markets || "").trim();
  const nbaHoursRaw = body.nba_hours ?? body.hours;
  const nbaHours =
    (sport === "nba" || sport === "euroleague") && nbaHoursRaw !== undefined && nbaHoursRaw !== null
      ? Number(nbaHoursRaw)
      : undefined;
  const useRotowire = Boolean(body.use_rotowire ?? body.rotowire);
  const usePinnacle = Boolean(body.use_pinnacle ?? body.pinnacle);
  const response = runnerEnabled()
    ? await triggerRunner(match, sport, markets, nbaHours, useRotowire, usePinnacle)
    : await triggerWorkflow(match, "live");
  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}
