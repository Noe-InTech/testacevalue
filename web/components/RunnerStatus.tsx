"use client";

import { useCallback, useEffect, useState } from "react";

import type { RunnerHealth } from "@/lib/runner";

const POLL_MS = 8_000;

function formatTime(value?: string): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function statusLabel(status?: string): string {
  switch (status) {
    case "running":
      return "en cours";
    case "success":
      return "ok";
    case "error":
      return "erreur";
    case "cancelled":
      return "annulé";
    case "idle":
      return "idle";
    default:
      return status || "—";
  }
}

export function RunnerStatus() {
  const [health, setHealth] = useState<RunnerHealth | null>(null);
  const [open, setOpen] = useState(false);
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

  const reachable = Boolean(health?.reachable);
  const running = Boolean(health?.running);
  const tone = !health
    ? "unknown"
    : !health.configured
      ? "warn"
      : reachable
        ? running
          ? "busy"
          : "ok"
        : "down";

  const title = !health
    ? "Runner…"
    : !health.configured
      ? "Runner non configuré"
      : reachable
        ? running
          ? `Runner actif · ${health.sport || "?"}`
          : "Runner en ligne"
        : "Runner hors ligne";

  const sports = health?.sports_status
    ? Object.entries(health.sports_status)
    : [];

  return (
    <section className={`runner-status panel tone-${tone}`}>
      <button type="button" className="runner-status-toggle" onClick={() => setOpen((value) => !value)}>
        <span className={`runner-status-dot tone-${tone}`} aria-hidden="true" />
        <span className="runner-status-summary">
          <strong>{title}</strong>
          <span>
            {health?.runner_host ? health.runner_host : "proxy Vercel → EU"}
            {health?.fetched_at ? ` · ${formatTime(health.fetched_at)}` : ""}
            {checking ? " · maj…" : ""}
          </span>
        </span>
        <span className="runner-status-chevron">{open ? "▾" : "▸"}</span>
      </button>

      {open ? (
        <div className="runner-status-body">
          {!health?.configured ? (
            <p className="runner-status-note">
              Ajoute <code>RUNNER_URL</code> et <code>RUNNER_SECRET</code> sur Vercel pour voir l’état
              du runner EU ici.
            </p>
          ) : null}
          {health?.error && !reachable ? (
            <p className="runner-status-note danger-text">{health.error}</p>
          ) : null}
          {reachable && running ? (
            <p className="runner-status-note">
              Comparaison en cours : <strong>{health?.sport || "?"}</strong>
            </p>
          ) : null}
          {sports.length > 0 ? (
            <ul className="runner-status-sports">
              {sports.map(([sport, status]) => (
                <li key={sport}>
                  <span className="sport-name">{sport}</span>
                  <span className={`sport-pill status-${status.status || "idle"}`}>
                    {statusLabel(status.status)}
                  </span>
                  <span className="sport-msg" title={status.message || ""}>
                    {status.message || "—"}
                    {typeof status.comparable_count === "number"
                      ? ` · ${status.comparable_count} ligne(s)`
                      : ""}
                  </span>
                  <span className="sport-time">{formatTime(status.updated_at)}</span>
                </li>
              ))}
            </ul>
          ) : null}
          <div className="runner-status-actions">
            <button type="button" onClick={() => void refresh()} disabled={checking}>
              {checking ? "Actualisation…" : "Actualiser"}
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
