import { NextResponse } from "next/server";

import { fetchRunnerHealth } from "@/lib/runner";

export const dynamic = "force-dynamic";

export async function GET() {
  const health = await fetchRunnerHealth();
  return NextResponse.json(health, {
    status: health.configured && health.reachable ? 200 : health.configured ? 502 : 503,
  });
}
