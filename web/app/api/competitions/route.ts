import { NextResponse } from "next/server";

import { runnerEnabled, fetchRunnerCompetitions } from "@/lib/runner";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const sport = (searchParams.get("sport") || "soccer").trim().toLowerCase();

  if (!runnerEnabled()) {
    return NextResponse.json(
      { error: "RUNNER_URL / RUNNER_SECRET manquants sur Vercel." },
      { status: 500 },
    );
  }

  const response = await fetchRunnerCompetitions(sport);
  const data = await response.json().catch(() => ({}));
  return NextResponse.json(data, { status: response.status });
}
