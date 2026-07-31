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

export async function triggerWorkflow(match: string, mode: string = "live"): Promise<Response> {
  return dispatchGithubWorkflow("aces-compare.yml", { match, mode });
}

export async function triggerRepairRunnerWorkflow(reason = "site"): Promise<Response> {
  return dispatchGithubWorkflow("repair-runner.yml", { reason });
}

async function dispatchGithubWorkflow(
  workflowFile: string,
  inputs: Record<string, string>,
): Promise<Response> {
  const token = process.env.GITHUB_TOKEN?.trim();
  const { owner, repo } = githubConfig();
  if (!token || !owner || !repo) {
    return new Response(
      JSON.stringify({ error: "Configuration GitHub manquante sur Vercel (GITHUB_TOKEN / OWNER / REPO)." }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }

  const response = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${workflowFile}/dispatches`,
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
        inputs,
      }),
    },
  );

  if (!response.ok) {
    const detail = await response.text();
    return new Response(
      JSON.stringify({
        error: `Impossible de lancer GitHub Actions (${workflowFile}).`,
        detail,
      }),
      { status: response.status, headers: { "Content-Type": "application/json" } },
    );
  }

  return new Response(
    JSON.stringify({
      ok: true,
      workflow: workflowFile,
      message:
        workflowFile === "repair-runner.yml"
          ? "Réparation lancée via GitHub Actions — attends ~1–2 min puis Rafraîchir."
          : "Workflow lancé.",
    }),
    {
      status: 200,
      headers: { "Content-Type": "application/json" },
    },
  );
}

export function isAuthorized(secret: string | null | undefined): boolean {
  const expected = process.env.TRIGGER_SECRET?.trim();
  if (!expected) {
    return false;
  }
  return secret === expected;
}
