import { NextResponse } from "next/server";
import { readFile } from "node:fs/promises";
import path from "node:path";

import { fetchGithubJson } from "@/lib/github";
import { fetchRunnerResults, runnerEnabled } from "@/lib/runner";
import type { AcesPayload, RunStatus } from "@/lib/types";

async function readLocalJson<T>(filename: string): Promise<T | null> {
  try {
    const filePath = path.join(process.cwd(), "public", filename);
    const raw = await readFile(filePath, "utf-8");
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

const idlePayload: AcesPayload = {
  source: "tennis_aces_comparable",
  generated_at: "",
  comparable_count: 0,
  fr_higher_count: 0,
  value_count: 0,
  fr_only_count: 0,
  comparables: [],
  fr_higher_comparables: [],
  value_comparables: [],
  fr_only_comparables: [],
};

const runnerUnreachableStatus: RunStatus = {
  status: "error",
  message:
    "Runner EU injoignable depuis Vercel. Verifie RUNNER_URL (URL Cloudflare https://....trycloudflare.com, pas l'IP Oracle) puis redeploy.",
  updated_at: new Date().toISOString(),
};

export async function GET() {
  if (runnerEnabled()) {
    const runnerData = await fetchRunnerResults();
    if (runnerData) {
      return NextResponse.json({
        payload: runnerData.payload,
        status: runnerData.status,
        source: "runner-live",
        fetched_at: new Date().toISOString(),
      });
    }

    return NextResponse.json({
      payload: idlePayload,
      status: runnerUnreachableStatus,
      source: "runner-unreachable",
      fetched_at: new Date().toISOString(),
    });
  }

  const [payload, status] = await Promise.all([
    fetchGithubJson<AcesPayload>("web/public/latest_aces.json"),
    fetchGithubJson<RunStatus>("web/public/run_status.json"),
  ]);

  const localPayload = payload ?? (await readLocalJson<AcesPayload>("latest_aces.json"));
  const localStatus = status ?? (await readLocalJson<RunStatus>("run_status.json"));

  return NextResponse.json({
    payload: localPayload,
    status: localStatus,
    fetched_at: new Date().toISOString(),
  });
}
