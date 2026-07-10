"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { ResultsTable } from "@/components/ResultsTable";
import type { AcesPayload, RunStatus } from "@/lib/types";

const SECRET_STORAGE_KEY = "aces_trigger_secret";

function formatTimestamp(value?: string): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("fr-FR");
}

export function Dashboard() {
  const [secret, setSecret] = useState("");
  const [match, setMatch] = useState("");
  const [payload, setPayload] = useState<AcesPayload | null>(null);
  const [status, setStatus] = useState<RunStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  useEffect(() => {
    const saved = window.localStorage.getItem(SECRET_STORAGE_KEY);
    if (saved) {
      setSecret(saved);
    }
  }, []);

  const refresh = useCallback(async () => {
    const response = await fetch("/api/results", { cache: "no-store" });
    if (!response.ok) {
      throw new Error("Impossible de charger les resultats.");
    }
    const data = await response.json();
    setPayload(data.payload ?? null);
    setStatus(data.status ?? null);
    return data as { payload: AcesPayload | null; status: RunStatus | null };
  }, []);

  useEffect(() => {
    refresh().catch((exc) => setError(exc instanceof Error ? exc.message : "Erreur inconnue."));
  }, [refresh]);

  const waitForCompletion = useCallback(
    async (startedAt: number) => {
      const deadline = Date.now() + 3 * 60 * 1000;
      while (Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 3000));
        const data = await refresh();
        const currentStatus = data.status?.status;
        const generatedAt = data.payload?.generated_at
          ? new Date(data.payload.generated_at).getTime()
          : 0;
        const updatedAt = data.status?.updated_at
          ? new Date(data.status.updated_at).getTime()
          : 0;

        if ((data as { source?: string }).source === "runner-unreachable") {
          throw new Error(
            "Runner EU injoignable. Mets a jour RUNNER_URL sur Vercel (URL Cloudflare).",
          );
        }

        if (currentStatus === "error") {
          throw new Error(data.status?.message || "La comparaison a echoue.");
        }

        if (currentStatus === "success") {
          if (generatedAt >= startedAt - 5000 || updatedAt >= startedAt - 5000) {
            return;
          }
        }
      }
      throw new Error("Delai depasse (~3 min). Recharge la page.");
    },
    [refresh],
  );

  const onSubmit = async () => {
    setError("");
    setInfo("");
    if (!secret.trim()) {
      setError("Saisis ton code secret.");
      return;
    }

    window.localStorage.setItem(SECRET_STORAGE_KEY, secret.trim());
    setBusy(true);
    setInfo("Lancement en cours... (~30 s)");

    try {
      const startedAt = Date.now();
      const response = await fetch("/api/trigger", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ secret: secret.trim(), match: match.trim() }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Echec du declenchement.");
      }

      setInfo("Scrape live en cours... (~25 s)");
      await waitForCompletion(startedAt);
      setInfo("Comparaison terminee.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Erreur inconnue.");
    } finally {
      setBusy(false);
    }
  };

  const frHigherRows = useMemo(
    () => payload?.fr_higher_comparables ?? [],
    [payload],
  );

  return (
    <main className="page">
      <header className="hero">
        <p className="eyebrow">Tennis aces</p>
        <h1>Aces tennis — books FR vs FanDuel</h1>
        <p className="lead">
          Compare les lignes <strong>aces</strong> (Unibet, Betclic, Winamax) avec FanDuel en live (~25 s).
        </p>
      </header>

      <section className="panel controls">
        <label>
          Code secret
          <input
            type="password"
            value={secret}
            onChange={(event) => setSecret(event.target.value)}
            placeholder="PIN choisi sur Vercel"
            autoComplete="current-password"
          />
        </label>
        <label>
          Filtre match (optionnel)
          <input
            type="text"
            value={match}
            onChange={(event) => setMatch(event.target.value)}
            placeholder="sinner, fery..."
          />
        </label>
        <button type="button" onClick={onSubmit} disabled={busy}>
          {busy ? "Comparaison en cours..." : "Lancer comparaison live"}
        </button>
        {info ? <p className="info">{info}</p> : null}
        {error ? <p className="error">{error}</p> : null}
      </section>

      <section className="panel meta">
        <div>
          <span className="meta-label">Derniere mise a jour</span>
          <strong>{formatTimestamp(payload?.generated_at)}</strong>
        </div>
        <div>
          <span className="meta-label">Statut</span>
          <strong>{status?.status ?? "idle"}</strong>
        </div>
        <div>
          <span className="meta-label" title="Nombre de lignes aces alignees entre un book FR et FanDuel">
            Lignes comparees
          </span>
          <strong>{payload?.comparable_count ?? 0}</strong>
        </div>
        <div>
          <span
            className="meta-label"
            title="Lignes ou la cote FR est strictement superieure a FanDuel"
          >
            FR paie mieux
          </span>
          <strong>{payload?.fr_higher_count ?? 0}</strong>
        </div>
      </section>

      <ResultsTable
        title="Toutes les lignes aces comparees"
        rows={payload?.comparables ?? []}
        emptyMessage="Aucun resultat pour le moment. Lance une comparaison."
      />

      <ResultsTable
        title="Lignes ou le book FR paie mieux que FanDuel"
        rows={frHigherRows}
        emptyMessage="Aucune ligne ou la cote FR bat FanDuel sur ce run."
      />
    </main>
  );
}
