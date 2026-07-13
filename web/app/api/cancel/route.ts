import { NextResponse } from "next/server";

import { isAuthorized } from "@/lib/github";
import { cancelRunner, runnerEnabled } from "@/lib/runner";

export async function POST(request: Request) {
  let body: { secret?: string; sport?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Corps JSON invalide." }, { status: 400 });
  }

  if (!isAuthorized(body.secret)) {
    return NextResponse.json({ error: "Code secret incorrect." }, { status: 401 });
  }

  if (!runnerEnabled()) {
    return NextResponse.json(
      { error: "Arret indisponible sans runner EU (RUNNER_URL)." },
      { status: 503 },
    );
  }

  const sport = (body.sport || "tennis").trim().toLowerCase();
  const response = await cancelRunner(sport);
  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}
