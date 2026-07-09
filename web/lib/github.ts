const DEFAULT_BRANCH = "main";

function githubConfig() {
  const owner = process.env.GITHUB_OWNER?.trim();
  const repo = process.env.GITHUB_REPO?.trim();
  const branch = process.env.GITHUB_BRANCH?.trim() || DEFAULT_BRANCH;
  return { owner, repo, branch };
}

export function githubRawUrl(path: string): string | null {
  const { owner, repo, branch } = githubConfig();
  if (!owner || !repo) {
    return null;
  }
  return `https://raw.githubusercontent.com/${owner}/${repo}/${branch}/${path}`;
}

export async function fetchGithubJson<T>(path: string): Promise<T | null> {
  const url = githubRawUrl(path);
  if (!url) {
    return null;
  }
  const response = await fetch(url, {
    cache: "no-store",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    return null;
  }
  return (await response.json()) as T;
}

export async function triggerWorkflow(match: string): Promise<Response> {
  const token = process.env.GITHUB_TOKEN?.trim();
  const { owner, repo } = githubConfig();
  if (!token || !owner || !repo) {
    return new Response(
      JSON.stringify({ error: "Configuration GitHub manquante sur Vercel." }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }

  const response = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/actions/workflows/aces-compare.yml/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        ref: process.env.GITHUB_BRANCH?.trim() || DEFAULT_BRANCH,
        inputs: { match },
      }),
    },
  );

  if (!response.ok) {
    const detail = await response.text();
    return new Response(
      JSON.stringify({ error: "Impossible de lancer GitHub Actions.", detail }),
      { status: response.status, headers: { "Content-Type": "application/json" } },
    );
  }

  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

export function isAuthorized(secret: string | null | undefined): boolean {
  const expected = process.env.TRIGGER_SECRET?.trim();
  if (!expected) {
    return false;
  }
  return secret === expected;
}
