import { NextResponse } from "next/server";

import { isAuthorized, triggerRepairRunnerWorkflow } from "@/lib/github";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  let body: { secret?: string; reason?: string } = {};
  try {
    body = await request.json();
  } catch {
    body = {};
  }

  if (!isAuthorized(body.secret)) {
    return NextResponse.json({ error: "Code secret incorrect." }, { status: 401 });
  }

  const response = await triggerRepairRunnerWorkflow(
    (body.reason || "site").trim() || "site",
  );
  const data = await response.json().catch(() => ({}));
  return NextResponse.json(data, { status: response.status });
}
