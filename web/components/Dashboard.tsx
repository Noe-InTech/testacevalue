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
    return data as {
      payload: AcesPayload | null;
      status: RunStatus | null;
      source?: string;
    };
  }, []);

  useEffect(() => {
    refresh().catch((exc) => setError(exc instanceof Error ? exc.message : "Erreur inconnue."));
  }, [refresh]);

  useEffect(() => {
    if (!busy) {
      return;
    }
    const timer = window.setInterval(() => {
      refresh().catch(() => undefined);
    }, 500);
    return () => window.clearInterval(timer);
  }, [busy, refresh]);

  const waitForCompletion = useCallback(
    async () => {
      const deadline = Date.now() + 5 * 60 * 1000;
      let lastCount = 0;
      let stalePolls = 0;

      while (Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 500));
        const data = await refresh();
        const currentStatus = data.status?.status;
        const rowCount = data.payload?.comparable_count ?? 0;
        const isFinalPayload = data.payload?.partial === false;

        if (rowCount > lastCount) {
          lastCount = rowCount;
          stalePolls = 0;
          setInfo(`${rowCount} ligne(s) affichee(s), comparaison en cours...`);
        } else if (currentStatus === "running") {
          setInfo(data.status?.message || "Comparaison en cours...");
        }

        if (data.source === "runner-unreachable") {
          throw new Error(
            "Runner EU injoignable. Mets a jour RUNNER_URL sur Vercel (URL Cloudflare).",
          );
        }

        if (currentStatus === "error") {
          if (rowCount > 0) {
            setInfo(`${rowCount} ligne(s) affichees (comparaison partielle).`);
            return;
          }
          throw new Error(data.status?.message || "La comparaison a echoue.");
        }

        if (currentStatus === "success" || isFinalPayload) {
          return;
        }

        if (rowCount > 0) {
          stalePolls += 1;
          if (stalePolls >= 20 && currentStatus !== "running") {
            setInfo(`${rowCount} ligne(s) affichees.`);
            return;
          }
        }
      }

      const finalData = await refresh();
      const finalCount = finalData.payload?.comparable_count ?? 0;
      if (finalCount > 0) {
        setInfo(`${finalCount} ligne(s) affichees (delai max atteint).`);
        return;
      }
      throw new Error("Delai depasse (~5 min). Recharge la page.");
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
    setPayload({
      source: "tennis_aces_comparable",
      generated_at: "",
      partial: true,
      comparable_count: 0,
      fr_higher_count: 0,
      comparables: [],
      fr_higher_comparables: [],
    });
    setInfo("Lancement en cours...");

    try {
      const response = await fetch("/api/trigger", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ secret: secret.trim(), match: match.trim() }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Echec du declenchement.");
      }

      setInfo("Scrape live en cours...");
      await waitForCompletion();
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
  const frOnlyRows = useMemo(() => payload?.fr_only_comparables ?? [], [payload]);

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
          <span className="meta-label">Etape</span>
          <strong>{status?.message ?? "—"}</strong>
        </div>
        <div>
          <span className="meta-label">Statut</span>
          <strong>
            {status?.status ?? "idle"}
            {payload?.partial ? " (partiel)" : ""}
          </strong>
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
        <div>
          <span className="meta-label" title="Lignes aces FR sans equivalent FanDuel sur la meme ligne">
            FR sans FD
          </span>
          <strong>{payload?.fr_only_count ?? 0}</strong>
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

      <ResultsTable
        title="Lignes aces FR sans equivalent FanDuel (meme seuil)"
        rows={frOnlyRows}
        emptyMessage="Toutes les lignes FR ont un equivalent FanDuel, ou pas de marche aces FR."
      />
    </main>
  );
}
