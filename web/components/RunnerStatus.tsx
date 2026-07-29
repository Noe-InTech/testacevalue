"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import type { RunnerHealth } from "@/lib/runner";

const POLL_MS = 15_000;

export function RunnerStatus() {
  const [health, setHealth] = useState<RunnerHealth | null>(null);
  const [copied, setCopied] = useState(false);
  const [checking, setChecking] = useState(false);

  const refresh = useCallback(async () => {
    setChecking(true);
    try {
      const response = await fetch("/api/runner-health", { cache: "no-store" });
      const data = (await response.json()) as RunnerHealth;
      setHealth(data);
    } catch (error) {
      setHealth({
        ok: false,
        running: false,
        sport: "",
        reachable: false,
        configured: true,
        error: error instanceof Error ? error.message : "échec health check",
      });
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => {
      void refresh();
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const url = useMemo(() => {
    const live = health?.public_url?.trim().replace(/\/$/, "") || "";
    const configured = health?.configured_url?.trim().replace(/\/$/, "") || "";
    return live || configured;
  }, [health]);

  const mismatch =
    Boolean(health?.public_url) &&
    Boolean(health?.configured_url) &&
    health!.public_url!.replace(/\/$/, "") !== health!.configured_url!.replace(/\/$/, "");

  const onCopy = async () => {
    if (!url) {
      return;
    }
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      // Fallback for older browsers / insecure context
      const input = document.createElement("input");
      input.value = url;
      document.body.appendChild(input);
      input.select();
      document.execCommand("copy");
      document.body.removeChild(input);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    }
  };

  return (
    <section className="runner-link panel">
      <div className="runner-link-header">
        <strong>Lien runner (Cloudflare)</strong>
        <button type="button" className="runner-link-refresh" onClick={() => void refresh()} disabled={checking}>
          {checking ? "…" : "Rafraîchir"}
        </button>
      </div>

      {!health?.configured ? (
        <p className="runner-status-note">
          Configure <code>RUNNER_URL</code> sur Vercel pour afficher le lien ici.
        </p>
      ) : null}

      {health?.configured && !url ? (
        <p className="runner-status-note danger-text">
          Lien introuvable pour l’instant
          {health.error ? ` (${health.error})` : ""}. Redémarre le tunnel sur la VM ou réessaie.
        </p>
      ) : null}

      {url ? (
        <div className="runner-link-row">
          <code className="runner-link-url" title={url}>
            {url}
          </code>
          <button type="button" className="runner-link-copy" onClick={() => void onCopy()}>
            {copied ? "Copié" : "Copier"}
          </button>
        </div>
      ) : null}

      {mismatch ? (
        <p className="runner-status-note">
          Le tunnel live diffère de <code>RUNNER_URL</code> sur Vercel — mets à jour la variable puis
          redeploy.
        </p>
      ) : null}
    </section>
  );
}
