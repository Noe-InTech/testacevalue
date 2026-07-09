import { NextResponse } from "next/server";

import { isAuthorized, triggerWorkflow } from "@/lib/github";

export async function POST(request: Request) {
  let body: { secret?: string; match?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Corps JSON invalide." }, { status: 400 });
  }

  if (!isAuthorized(body.secret)) {
    return NextResponse.json({ error: "Code secret incorrect." }, { status: 401 });
  }

  const match = (body.match || "").trim();
  const response = await triggerWorkflow(match);
  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}
