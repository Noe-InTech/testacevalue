import { NextResponse } from "next/server";

import { isAuthorized } from "@/lib/github";
import { requestRunnerSelfUpdate } from "@/lib/runner";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  let body: { secret?: string; restart_tunnel?: boolean } = {};
  try {
    body = await request.json();
  } catch {
    body = {};
  }

  if (!isAuthorized(body.secret)) {
    return NextResponse.json({ error: "Code secret incorrect." }, { status: 401 });
  }

  const response = await requestRunnerSelfUpdate({
    restartTunnel: Boolean(body.restart_tunnel),
  });
  const data = await response.json().catch(() => ({}));
  return NextResponse.json(data, { status: response.status });
}
