import { NextResponse } from "next/server";

import { fetchAllRunnersHealth } from "@/lib/runner";

export async function GET() {
  const runners = await fetchAllRunnersHealth();
  return NextResponse.json({
    runners,
    fetched_at: new Date().toISOString(),
  });
}
