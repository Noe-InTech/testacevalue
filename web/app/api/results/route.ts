import { NextResponse } from "next/server";
import { readFile } from "node:fs/promises";
import path from "node:path";

import { fetchGithubJson } from "@/lib/github";
import { fetchRunnerResults, runnerEnabled } from "@/lib/runner";
import type { ApiPayload, MarketPayload, RunStatus, SportKey } from "@/lib/types";

async function readLocalJson<T>(filename: string): Promise<T | null> {
  try {
    const filePath = path.join(process.cwd(), "public", filename);
    const raw = await readFile(filePath, "utf-8");
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function emptyMarketPayload(source: string): MarketPayload {
  return {
    source,
    generated_at: "",
    anchors_total: 0,
    matches_done: 0,
    comparable_count: 0,
    fr_higher_count: 0,
    value_count: 0,
    fr_only_count: 0,
    fd_only_count: 0,
    comparables: [],
    fr_higher_comparables: [],
    value_comparables: [],
    fr_only_comparables: [],
    fd_only_comparables: [],
    match_progress: [],
  };
}

const idleWnbaPayload: MarketPayload = emptyMarketPayload("wnba_player_props_comparable");
const idleNbaPayload: MarketPayload = emptyMarketPayload("nba_player_props_comparable");

const idlePayload: ApiPayload = {
  source: "tennis_props_comparable",
  generated_at: "",
  partial: true,
  anchors_total: 0,
  matches_done: 0,
  aces: emptyMarketPayload("tennis_aces_comparable"),
  breaks: emptyMarketPayload("tennis_breaks_comparable"),
};

const runnerUnreachableStatus: RunStatus = {
  status: "error",
  message:
    "Runner EU injoignable depuis Vercel. Verifie RUNNER_URL (URL Cloudflare https://....trycloudflare.com, pas l'IP Oracle) puis redeploy.",
  updated_at: new Date().toISOString(),
};

export async function GET(request: Request) {
  const sport = (new URL(request.url).searchParams.get("sport") || "tennis") as SportKey;

  if (runnerEnabled()) {
    try {
      const runnerData = await fetchRunnerResults(sport);
      if (runnerData) {
        return NextResponse.json({
          payload: runnerData.payload,
          status: runnerData.status,
          source: "runner-live",
          sport,
          fetched_at: new Date().toISOString(),
        });
      }
    } catch {
      // timeout ou runner injoignable — retomber sur le payload vide ci-dessous
    }

    return NextResponse.json({
      payload: sport === "wnba" ? idleWnbaPayload : sport === "nba" ? idleNbaPayload : idlePayload,
      status: runnerUnreachableStatus,
      source: "runner-unreachable",
      sport,
      fetched_at: new Date().toISOString(),
    });
  }

  const [payload, status] = await Promise.all([
    fetchGithubJson<ApiPayload>("web/public/latest_aces.json"),
    fetchGithubJson<RunStatus>("web/public/run_status.json"),
  ]);

  const localPayload = payload ?? (await readLocalJson<ApiPayload>("latest_aces.json"));
  const localStatus = status ?? (await readLocalJson<RunStatus>("run_status.json"));

  return NextResponse.json({
    payload: localPayload,
    status: localStatus,
    fetched_at: new Date().toISOString(),
  });
}
