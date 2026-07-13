function runnerConfig() {
  const baseUrl = process.env.RUNNER_URL?.trim().replace(/\/$/, "");
  const secret = process.env.RUNNER_SECRET?.trim();
  return { baseUrl, secret };
}

export function runnerEnabled(): boolean {
  const { baseUrl, secret } = runnerConfig();
  return Boolean(baseUrl && secret);
}

export async function triggerRunner(match: string, sport = "tennis"): Promise<Response> {
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
      body: JSON.stringify({ match, sport }),
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

export async function fetchRunnerResults(sport = "tennis"): Promise<{
  payload: unknown;
  status: unknown;
} | null> {
  const { baseUrl } = runnerConfig();
  if (!baseUrl) {
    return null;
  }
  const response = await fetch(`${baseUrl}/api/results?sport=${encodeURIComponent(sport)}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(15_000),
  });
  if (!response.ok) {
    return null;
  }
  return response.json();
}
