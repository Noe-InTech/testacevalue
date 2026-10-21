"use client";

import { useCallback, useEffect, useState } from "react";

import type { RunnerRegionHealth } from "@/lib/runner";

function statusLabel(runner: RunnerRegionHealth): string {
  if (!runner.configured) {
    return "Non configure";
  }
  if (!runner.ok) {
    return runner.error ? `Hors ligne (${runner.error})` : "Hors ligne";
  }
  if (runner.running) {
    return runner.sport ? `Actif (${runner.sport})` : "Comparaison en cours";
  }
  return runner.role === "us" ? "Pret (Bet365 US / sites US)" : "Pret";
}

function dotClass(runner: RunnerRegionHealth): string {
  if (!runner.configured) {
    return "runner-dot muted";
  }
  if (!runner.ok) {
    return "runner-dot error";
  }
  if (runner.running) {
    return "runner-dot busy";
  }
  return "runner-dot ok";
}

const EMPTY_EU: RunnerRegionHealth = {
  region: "eu",
  label: "France / EU",
  configured: false,
  ok: false,
  running: false,
  sport: "",
  fetched_at: "",
};

const EMPTY_US: RunnerRegionHealth = {
  region: "us",
  label: "US",
  configured: false,
  ok: false,
  running: false,
  sport: "",
  fetched_at: "",
};

export function RunnerStatusBar() {
  const [runners, setRunners] = useState<RunnerRegionHealth[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/api/runners", { cache: "no-store" });
      if (!response.ok) {
        return;
      }
      const data = (await response.json()) as { runners?: RunnerRegionHealth[] };
      if (Array.isArray(data.runners)) {
        setRunners(data.runners);
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh().catch(() => undefined);
    const timer = window.setInterval(() => {
      refresh().catch(() => undefined);
    }, 30_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const eu = runners.find((r) => r.region === "eu") ?? EMPTY_EU;
  const us = runners.find((r) => r.region === "us") ?? EMPTY_US;

  return (
    <section className="panel runner-status-bar" aria-label="Etat des runners cloud">
      <div className="runner-status-header">
        <h2>Runners cloud</h2>
        <button type="button" className="ghost-btn" onClick={() => refresh().catch(() => undefined)}>
          {loading ? "..." : "Rafraichir"}
        </button>
      </div>
      <ul className="runner-status-list">
        <li>
          <span className={dotClass(eu)} aria-hidden />
          <div>
            <strong>France / EU</strong>
            <span className="runner-status-detail">{loading && !runners.length ? "Chargement..." : statusLabel(eu)}</span>
          </div>
        </li>
        <li>
          <span className={dotClass(us)} aria-hidden />
          <div>
            <strong>Etats-Unis</strong>
            <span className="runner-status-detail">{loading && !runners.length ? "Chargement..." : statusLabel(us)}</span>
          </div>
        </li>
      </ul>
      <p className="runner-status-hint">
        Le site parle au runner FR (RUNNER_URL) pour lancer les compares. Le runner US (RUNNER_US_URL) sert Bet365 /
        sites US ; le runner FR l&apos;appelle via US_RUNNER_URL sur la VM France.
      </p>
    </section>
  );
}
