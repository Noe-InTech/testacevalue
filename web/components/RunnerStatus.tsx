"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import type { RunnerHealth } from "@/lib/runner";

const SECRET_STORAGE_KEY = "aces_trigger_secret";

export function RunnerStatus({ standalone = false }: { standalone?: boolean }) {
  const [open, setOpen] = useState(standalone);
  const [secret, setSecret] = useState("");
  const [unlocked, setUnlocked] = useState(false);
  const [health, setHealth] = useState<RunnerHealth | null>(null);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [copied, setCopied] = useState(false);
  const [checking, setChecking] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [repairing, setRepairing] = useState(false);

  useEffect(() => {
    const saved = window.localStorage.getItem(SECRET_STORAGE_KEY);
    if (saved) {
      setSecret(saved);
    }
  }, []);

  const refresh = useCallback(async (pin: string) => {
    const trimmed = pin.trim();
    if (!trimmed) {
      setError("Saisis ton code secret.");
      setUnlocked(false);
      setHealth(null);
      return;
    }
    setChecking(true);
    setError("");
    try {
      const response = await fetch("/api/runner-health", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ secret: trimmed }),
        cache: "no-store",
      });
      const data = await response.json();
      if (response.status === 401) {
        setUnlocked(false);
        setHealth(null);
        setError(data.error || "Code secret incorrect.");
        return;
      }
      if (!response.ok && !data?.configured) {
        setUnlocked(false);
        setHealth(null);
        setError(data.error || `HTTP ${response.status}`);
        return;
      }
      window.localStorage.setItem(SECRET_STORAGE_KEY, trimmed);
      setUnlocked(true);
      setHealth(data as RunnerHealth);
      if (data.configured && data.reachable === false) {
        setError(
          String(
            data.error ||
              "Runner injoignable (tunnel mort). Clique « Réparer le runner ».",
          ),
        );
      } else if (data.error && !data.public_url && !data.configured_url) {
        setError(String(data.error));
      } else {
        setError("");
      }
    } catch (exc) {
      setUnlocked(false);
      setHealth(null);
      setError(exc instanceof Error ? exc.message : "échec health check");
    } finally {
      setChecking(false);
    }
  }, []);

  const onUpdate = useCallback(async () => {
    const trimmed = secret.trim();
    if (!trimmed) {
      setError("Saisis ton code secret.");
      return;
    }
    setUpdating(true);
    setError("");
    setInfo("");
    try {
      const response = await fetch("/api/runner-update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ secret: trimmed }),
        cache: "no-store",
      });
      const data = await response.json();
      if (response.status === 401) {
        setError(data.error || "Code secret incorrect.");
        return;
      }
      if (!response.ok) {
        setError(data.error || data.message || `HTTP ${response.status}`);
        return;
      }
      setInfo(
        data.message ||
          "Mise à jour lancée — le runner redémarre. Attends ~10s puis rafraîchis.",
      );
      window.setTimeout(() => {
        void refresh(trimmed);
      }, 8000);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "échec mise à jour");
    } finally {
      setUpdating(false);
    }
  }, [secret, refresh]);

  const onRepair = useCallback(async () => {
    const trimmed = secret.trim();
    if (!trimmed) {
      setError("Saisis ton code secret.");
      return;
    }
    setRepairing(true);
    setError("");
    setInfo("");
    try {
      const response = await fetch("/api/runner-repair", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ secret: trimmed, reason: "site" }),
        cache: "no-store",
      });
      const data = await response.json();
      if (response.status === 401) {
        setError(data.error || "Code secret incorrect.");
        return;
      }
      if (!response.ok) {
        setError(data.error || data.detail || `HTTP ${response.status}`);
        return;
      }
      setInfo(
        data.message ||
          "Réparation lancée via GitHub — attends ~1–2 min puis Rafraîchir.",
      );
      window.setTimeout(() => {
        void refresh(trimmed);
      }, 90_000);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "échec réparation");
    } finally {
      setRepairing(false);
    }
  }, [secret, refresh]);

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
    } catch {
      const input = document.createElement("input");
      input.value = url;
      document.body.appendChild(input);
      input.select();
      document.execCommand("copy");
      document.body.removeChild(input);
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  };

  const onUnlock = () => {
    void refresh(secret);
  };

  const onClose = () => {
    if (standalone) {
      setUnlocked(false);
      setHealth(null);
      setError("");
      setInfo("");
      setCopied(false);
      return;
    }
    setOpen(false);
    setUnlocked(false);
    setHealth(null);
    setError("");
    setInfo("");
    setCopied(false);
  };

  if (!open && !standalone) {
    return (
      <div className="runner-vault">
        <button type="button" className="runner-vault-trigger" onClick={() => setOpen(true)} title="Outils">
          ···
        </button>
      </div>
    );
  }

  const lastUpdate = health?.last_update;

  return (
    <div className={`runner-vault${standalone ? " runner-vault-standalone" : ""}`}>
      <section className="runner-link panel">
        <div className="runner-link-header">
          <strong>Lien runner</strong>
          {!standalone ? (
            <button type="button" className="runner-link-refresh" onClick={onClose}>
              Fermer
            </button>
          ) : unlocked ? (
            <button type="button" className="runner-link-refresh" onClick={onClose}>
              Masquer
            </button>
          ) : null}
        </div>

        {!unlocked ? (
          <div className="runner-vault-unlock">
            <label>
              Code secret
              <input
                type="password"
                value={secret}
                onChange={(event) => setSecret(event.target.value)}
                placeholder="Même PIN que pour lancer"
                autoComplete="current-password"
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    onUnlock();
                  }
                }}
              />
            </label>
            <button type="button" className="runner-link-copy" onClick={onUnlock} disabled={checking}>
              {checking ? "Vérification…" : "Afficher le lien"}
            </button>
          </div>
        ) : null}

        {error ? <p className="runner-status-note danger-text">{error}</p> : null}
        {info ? <p className="runner-status-note">{info}</p> : null}

        {unlocked ? (
          <>
            <div className="runner-link-header">
              <span className="runner-status-note">
                {health?.git_head ? `Commit VM : ${health.git_head}` : "Page privée"}
                {lastUpdate?.after
                  ? ` · dernier update ${lastUpdate.after}${lastUpdate.changed === false ? " (déjà à jour)" : ""}`
                  : ""}
              </span>
              <button
                type="button"
                className="runner-link-refresh"
                onClick={() => void refresh(secret)}
                disabled={checking || updating || repairing}
              >
                {checking ? "…" : "Rafraîchir"}
              </button>
            </div>

            {!url ? (
              <p className="runner-status-note danger-text">
                Lien introuvable pour l’instant. Utilise « Réparer le runner » ou redémarre le
                tunnel sur la VM.
              </p>
            ) : (
              <div className="runner-link-row">
                <code className="runner-link-url" title={url}>
                  {url}
                </code>
                <button type="button" className="runner-link-copy" onClick={() => void onCopy()}>
                  {copied ? "Copié" : "Copier"}
                </button>
              </div>
            )}

            <div className="runner-update-row">
              <button
                type="button"
                className="runner-update-btn"
                onClick={() => void onRepair()}
                disabled={repairing || checking || updating}
              >
                {repairing ? "Réparation…" : "Réparer le runner"}
              </button>
              <p className="runner-status-note">
                Redémarre VM + tunnel via GitHub Actions — marche même si le lien est mort (HTTP
                530). Attends ~1–2 min puis Rafraîchir.
              </p>
            </div>

            <div className="runner-update-row">
              <button
                type="button"
                className="runner-update-btn"
                onClick={() => void onUpdate()}
                disabled={
                  updating ||
                  checking ||
                  repairing ||
                  Boolean(health?.running) ||
                  health?.reachable === false
                }
              >
                {updating
                  ? "Mise à jour…"
                  : health?.running
                    ? "Compare en cours…"
                    : health?.reachable === false
                      ? "Tunnel mort — utilise Réparer"
                      : "Mettre à jour le runner"}
              </button>
              <p className="runner-status-note">
                git pull + restart quand le tunnel répond. Impossible pendant une comparaison.
              </p>
            </div>

            {mismatch ? (
              <p className="runner-status-note">
                Le tunnel live diffère de <code>RUNNER_URL</code> sur Vercel — mets à jour la variable
                puis redeploy (ou lance « Réparer le runner »).
              </p>
            ) : null}
          </>
        ) : null}
      </section>
    </div>
  );
}
