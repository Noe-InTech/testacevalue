function runnerConfig() {
  const baseUrl = process.env.RUNNER_URL?.trim().replace(/\/$/, "");
  const secret = process.env.RUNNER_SECRET?.trim();
  return { baseUrl, secret };
}

export function runnerEnabled(): boolean {
  const { baseUrl, secret } = runnerConfig();
  return Boolean(baseUrl && secret);
}

export async function triggerRunner(
  match: string,
  sport = "tennis",
  markets = "",
  nbaHours?: number,
  useRotowire = false,
): Promise<Response> {
  const { baseUrl, secret } = runnerConfig();
  if (!baseUrl || !secret) {
    return new Response(
      JSON.stringify({ error: "RUNNER_URL / RUNNER_SECRET manquants sur Vercel." }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }

  let response: Response;
  try {
    response = await fetch(`${baseUrl}/api/trigger`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Runner-Secret": secret,
      },
      body: JSON.stringify({
        match,
        sport,
        markets: markets || undefined,
        ...(sport === "nba" && typeof nbaHours === "number"
          ? { nba_hours: nbaHours }
          : {}),
        ...((sport === "nba" || sport === "wnba") && useRotowire
          ? { use_rotowire: true }
          : {}),
      }),
      cache: "no-store",
      signal: AbortSignal.timeout(20_000),
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : "connexion impossible";
    return new Response(
      JSON.stringify({
        error: `Runner EU injoignable (${detail}). RUNNER_URL doit etre l'URL Cloudflare https://....trycloudflare.com.`,
      }),
      { status: 502, headers: { "Content-Type": "application/json" } },
    );
  }

  const data = await response.json().catch(() => ({}));
  return new Response(JSON.stringify(data), {
    status: response.status,
    headers: { "Content-Type": "application/json" },
  });
}

export async function cancelRunner(sport = "tennis"): Promise<Response> {
  const { baseUrl, secret } = runnerConfig();
  if (!baseUrl || !secret) {
    return new Response(
      JSON.stringify({ error: "RUNNER_URL / RUNNER_SECRET manquants sur Vercel." }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }

  let response: Response;
  try {
    response = await fetch(`${baseUrl}/api/cancel`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Runner-Secret": secret,
      },
      body: JSON.stringify({ sport }),
      cache: "no-store",
      signal: AbortSignal.timeout(20_000),
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : "connexion impossible";
    return new Response(
      JSON.stringify({
        error: `Runner EU injoignable (${detail}).`,
      }),
      { status: 502, headers: { "Content-Type": "application/json" } },
    );
  }

  const data = await response.json().catch(() => ({}));
  return new Response(JSON.stringify(data), {
    status: response.status,
    headers: { "Content-Type": "application/json" },
  });
}

export async function fetchRunnerCompetitions(sport = "soccer"): Promise<Response> {
  const { baseUrl } = runnerConfig();
  if (!baseUrl) {
    return new Response(
      JSON.stringify({ error: "RUNNER_URL manquant sur Vercel." }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }

  try {
    const response = await fetch(
      `${baseUrl}/api/competitions?sport=${encodeURIComponent(sport)}`,
      {
        cache: "no-store",
        signal: AbortSignal.timeout(30_000),
      },
    );
    const data = await response.json().catch(() => ({}));
    return new Response(JSON.stringify(data), {
      status: response.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : "connexion impossible";
    return new Response(
      JSON.stringify({ error: `Runner EU injoignable (${detail}).` }),
      { status: 502, headers: { "Content-Type": "application/json" } },
    );
  }
}

export async function fetchRunnerResults(sport = "tennis"): Promise<{
  payload: unknown;
  status: unknown;
} | null> {
  const { baseUrl } = runnerConfig();
  if (!baseUrl) {
    return null;
  }
  try {
    const response = await fetch(`${baseUrl}/api/results?sport=${encodeURIComponent(sport)}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(60_000),
    });
    if (!response.ok) {
      return null;
    }
    return response.json();
  } catch {
    return null;
  }
}

export interface RunnerSportStatus {
  status?: string;
  message?: string;
  updated_at?: string;
  match_filter?: string;
  matches_done?: number;
  anchors_total?: number;
  comparable_count?: number;
}

export interface RunnerLastUpdate {
  ok?: boolean;
  changed?: boolean;
  scheduled?: boolean;
  before?: string;
  after?: string;
  before_message?: string;
  after_message?: string;
  branch?: string;
  message?: string;
  scheduled_at?: string;
  finished_at?: string;
  error?: string;
}

export interface RunnerHealth {
  ok: boolean;
  running: boolean;
  sport: string;
  public_url?: string;
  configured_url?: string;
  sports?: string[];
  sports_status?: Record<string, RunnerSportStatus>;
  git_head?: string;
  last_update?: RunnerLastUpdate;
  fetched_at?: string;
  reachable: boolean;
  configured: boolean;
  error?: string;
  runner_host?: string;
}

export async function requestBetclicShare(options: {
  selectionId: string;
  matchId: string;
  marketId: string;
  matchUrl?: string;
}): Promise<Response> {
  const { baseUrl, secret } = runnerConfig();
  if (!baseUrl || !secret) {
    return new Response(
      JSON.stringify({ error: "RUNNER_URL / RUNNER_SECRET manquants sur Vercel." }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }

  try {
    const response = await fetch(`${baseUrl}/api/betclic-share`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Runner-Secret": secret,
      },
      body: JSON.stringify({
        selection_id: options.selectionId,
        match_id: options.matchId,
        market_id: options.marketId,
        match_url: options.matchUrl || "",
      }),
      cache: "no-store",
      signal: AbortSignal.timeout(45_000),
    });
    const data = await response.json().catch(() => ({}));
    return new Response(JSON.stringify(data), {
      status: response.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : "connexion impossible";
    return new Response(
      JSON.stringify({
        error: `Runner EU injoignable (${detail}).`,
      }),
      { status: 502, headers: { "Content-Type": "application/json" } },
    );
  }
}

export async function requestRunnerSelfUpdate(options?: {
  restartTunnel?: boolean;
}): Promise<Response> {
  const { baseUrl, secret } = runnerConfig();
  if (!baseUrl || !secret) {
    return new Response(
      JSON.stringify({ error: "RUNNER_URL / RUNNER_SECRET manquants sur Vercel." }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }

  try {
    const response = await fetch(`${baseUrl}/api/self-update`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Runner-Secret": secret,
      },
      body: JSON.stringify({ restart_tunnel: Boolean(options?.restartTunnel) }),
      cache: "no-store",
      signal: AbortSignal.timeout(20_000),
    });
    const data = await response.json().catch(() => ({}));
    return new Response(JSON.stringify(data), {
      status: response.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : "connexion impossible";
    return new Response(
      JSON.stringify({
        error: `Runner EU injoignable (${detail}).`,
      }),
      { status: 502, headers: { "Content-Type": "application/json" } },
    );
  }
}

export async function fetchRunnerHealth(): Promise<RunnerHealth> {
  const { baseUrl, secret } = runnerConfig();
  if (!baseUrl || !secret) {
    return {
      ok: false,
      running: false,
      sport: "",
      reachable: false,
      configured: false,
      error: "RUNNER_URL / RUNNER_SECRET manquants sur Vercel.",
    };
  }

  const configuredUrl = baseUrl.replace(/\/$/, "");
  let runnerHost = "";
  try {
    runnerHost = new URL(baseUrl).host;
  } catch {
    runnerHost = baseUrl;
  }

  try {
    const response = await fetch(`${baseUrl}/api/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(8_000),
    });
    if (!response.ok) {
      return {
        ok: false,
        running: false,
        sport: "",
        reachable: false,
        configured: true,
        configured_url: configuredUrl,
        runner_host: runnerHost,
        error: `HTTP ${response.status}`,
      };
    }
    const data = (await response.json()) as Omit<RunnerHealth, "reachable" | "configured">;
    return {
      ...data,
      ok: Boolean(data.ok),
      running: Boolean(data.running),
      sport: data.sport || "",
      public_url: typeof data.public_url === "string" ? data.public_url : "",
      configured_url: configuredUrl,
      git_head: typeof data.git_head === "string" ? data.git_head : "",
      last_update: data.last_update,
      reachable: true,
      configured: true,
      runner_host: runnerHost,
    };
  } catch (error) {
    const detail = error instanceof Error ? error.message : "connexion impossible";
    return {
      ok: false,
      running: false,
      sport: "",
      reachable: false,
      configured: true,
      configured_url: configuredUrl,
      runner_host: runnerHost,
      error: detail,
    };
  }
}

export type RunnerRegion = "eu" | "us";

export interface RunnerRegionHealth {
  region: RunnerRegion;
  label: string;
  configured: boolean;
  ok: boolean;
  running: boolean;
  sport: string;
  role?: string;
  error?: string;
  fetched_at: string;
}

function usRunnerConfig() {
  const baseUrl = process.env.RUNNER_US_URL?.trim().replace(/\/$/, "");
  const secret = (process.env.RUNNER_US_SECRET || process.env.RUNNER_SECRET)?.trim();
  return { baseUrl, secret };
}

export async function fetchUsRunnerHealth(): Promise<RunnerRegionHealth> {
  const { baseUrl } = usRunnerConfig();
  const fetched_at = new Date().toISOString();
  if (!baseUrl) {
    return {
      region: "us",
      label: "US",
      configured: false,
      ok: false,
      running: false,
      sport: "",
      error: "RUNNER_US_URL non configure sur Vercel (optionnel pour afficher l'etat US).",
      fetched_at,
    };
  }
  try {
    const response = await fetch(`${baseUrl}/api/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(12_000),
    });
    const data = (await response.json().catch(() => ({}))) as {
      ok?: boolean;
      running?: boolean;
      sport?: string;
      role?: string;
    };
    if (!response.ok) {
      return {
        region: "us",
        label: "US",
        configured: true,
        ok: false,
        running: false,
        sport: "",
        error: `HTTP ${response.status}`,
        fetched_at,
      };
    }
    return {
      region: "us",
      label: "US",
      configured: true,
      ok: Boolean(data.ok),
      running: Boolean(data.running),
      sport: String(data.sport || ""),
      role: typeof data.role === "string" ? data.role : "us",
      fetched_at,
    };
  } catch (error) {
    const detail = error instanceof Error ? error.message : "connexion impossible";
    return {
      region: "us",
      label: "US",
      configured: true,
      ok: false,
      running: false,
      sport: "",
      error: detail,
      fetched_at,
    };
  }
}

export async function fetchEuRunnerRegionHealth(): Promise<RunnerRegionHealth> {
  const health = await fetchRunnerHealth();
  const fetched_at = new Date().toISOString();
  if (!health.configured) {
    return {
      region: "eu",
      label: "France / EU",
      configured: false,
      ok: false,
      running: false,
      sport: "",
      error: health.error || "RUNNER_URL non configure sur Vercel.",
      fetched_at,
    };
  }
  return {
    region: "eu",
    label: "France / EU",
    configured: true,
    ok: health.reachable && health.ok,
    running: health.running,
    sport: health.sport,
    role: "eu",
    error: health.reachable ? health.error : health.error || "Runner FR injoignable.",
    fetched_at,
  };
}

/** Etat FR + US pour le bandeau du site (sans secret). */
export async function fetchAllRunnersHealth(): Promise<RunnerRegionHealth[]> {
  const [eu, us] = await Promise.all([fetchEuRunnerRegionHealth(), fetchUsRunnerHealth()]);
  return [eu, us];
}
