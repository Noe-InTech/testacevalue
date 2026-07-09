import { NextResponse } from "next/server";
import { readFile } from "node:fs/promises";
import path from "node:path";

import { fetchGithubJson } from "@/lib/github";
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

export async function GET() {
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
