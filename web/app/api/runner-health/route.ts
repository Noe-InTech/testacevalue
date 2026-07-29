import { NextResponse } from "next/server";

import { isAuthorized } from "@/lib/github";
import { fetchRunnerHealth } from "@/lib/runner";

export const dynamic = "force-dynamic";

function extractSecret(request: Request): string {
  const header =
    request.headers.get("X-Trigger-Secret")?.trim() ||
    request.headers.get("x-trigger-secret")?.trim() ||
    "";
  if (header) {
    return header;
  }
  try {
    const url = new URL(request.url);
    return url.searchParams.get("secret")?.trim() || "";
  } catch {
    return "";
  }
}

export async function GET(request: Request) {
  if (!isAuthorized(extractSecret(request))) {
    return NextResponse.json({ error: "Code secret incorrect." }, { status: 401 });
  }

  const health = await fetchRunnerHealth();
  return NextResponse.json(health, {
    status: health.configured && health.reachable ? 200 : health.configured ? 502 : 503,
  });
}

export async function POST(request: Request) {
  let body: { secret?: string } = {};
  try {
    body = await request.json();
  } catch {
    body = {};
  }
  const secret = body.secret?.trim() || extractSecret(request);
  if (!isAuthorized(secret)) {
    return NextResponse.json({ error: "Code secret incorrect." }, { status: 401 });
  }

  const health = await fetchRunnerHealth();
  return NextResponse.json(health, {
    status: health.configured && health.reachable ? 200 : health.configured ? 502 : 503,
  });
}
