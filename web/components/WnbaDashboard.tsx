"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { CollapsibleSection } from "@/components/CollapsibleSection";
import { ResultsTable } from "@/components/ResultsTable";
import type { MarketPayload, RunStatus } from "@/lib/types";
import { getPayloadProgressSnapshot } from "@/lib/types";

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

export function WnbaDashboard() {
  const [secret, setSecret] = useState("");
  const [match, setMatch] = useState("");
  const [progressSearch, setProgressSearch] = useState("");
  const [frOnlySearch, setFrOnlySearch] = useState("");
  const [fdOnlySearch, setFdOnlySearch] = useState("");
  const [payload, setPayload] = useState<MarketPayload | null>(null);
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
    const response = await fetch("/api/results?sport=wnba", { cache: "no-store" });
    if (!response.ok) {
      throw new Error("Impossible de charger les resultats WNBA.");
    }
    const data = await response.json();
    setPayload((data.payload as MarketPayload) ?? null);
    setStatus(data.status ?? null);
    return data as {
      payload: MarketPayload | null;
      status: RunStatus | null;
      source?: string;
    };
  }, []);

  useEffect(() => {
    refresh().catch((exc) => setError(exc instanceof Error ? exc.message : "Erreur inconnue."));
  }, [refresh]);

  useEffect(() => {
    if (!busy && status?.status !== "running") {
      return;
    }
    const timer = window.setInterval(() => {
      refresh().catch(() => undefined);
    }, 500);
    return () => window.clearInterval(timer);
  }, [busy, status?.status, refresh]);

  const waitForCompletion = useCallback(async () => {
    const deadline = Date.now() + 8 * 60 * 1000;
    let lastRows = 0;
    let lastMatches = 0;

    while (Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 500));
      const data = await refresh();
      const progress = getPayloadProgressSnapshot(data.payload);
      const currentStatus = data.status?.status;
      const comparableCount = progress.comparable_count;
      const frOnlyCount = progress.fr_only_count;
      const totalRows = comparableCount + frOnlyCount;
      const matchesDone = data.status?.matches_done ?? progress.matches_done;
      const anchorsTotal = data.status?.anchors_total ?? progress.anchors_total;
      const isFinalPayload = progress.partial === false;

      if (matchesDone > lastMatches || totalRows > lastRows) {
        lastMatches = matchesDone;
        lastRows = totalRows;
        if (anchorsTotal > 0) {
          setInfo(`${matchesDone}/${anchorsTotal} match(s) — ${totalRows} ligne(s) affichee(s)...`);
        } else {
          setInfo(`${totalRows} ligne(s) affichee(s), comparaison en cours...`);
        }
      } else if (currentStatus === "running") {
        setInfo(data.status?.message || "Comparaison WNBA en cours...");
      }

      if (data.source === "runner-unreachable") {
        throw new Error(
          "Runner EU injoignable. Mets a jour RUNNER_URL sur Vercel (URL Cloudflare).",
        );
      }

      if (currentStatus === "error") {
        if (totalRows > 0 || matchesDone > 0) {
          setInfo(`${matchesDone}/${anchorsTotal || "?"} match(s), ${totalRows} ligne(s) (partiel).`);
          return;
        }
        throw new Error(data.status?.message || "La comparaison WNBA a echoue.");
      }

      if (currentStatus === "success" || isFinalPayload) {
        return;
      }
    }

    const finalData = await refresh();
    const finalProgress = getPayloadProgressSnapshot(finalData.payload);
    const finalRows = finalProgress.comparable_count + finalProgress.fr_only_count;
    if (finalRows > 0 || (finalData.status?.matches_done ?? finalProgress.matches_done) > 0) {
      setInfo(`${finalRows} ligne(s) affichees (delai max atteint).`);
      return;
    }
    throw new Error("Delai depasse (~8 min). Recharge la page.");
  }, [refresh]);

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
      source: "wnba_player_props_comparable",
      generated_at: "",
      partial: true,
      comparable_count: 0,
      fr_higher_count: 0,
      comparables: [],
      fr_higher_comparables: [],
    });
    setInfo("Lancement WNBA en cours...");

    try {
      const response = await fetch("/api/trigger", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ secret: secret.trim(), match: match.trim(), sport: "wnba" }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Echec du declenchement.");
      }

      setInfo("Scrape WNBA live en cours...");
      await waitForCompletion();
      setInfo("Comparaison WNBA terminee.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Erreur inconnue.");
    } finally {
      setBusy(false);
    }
  };

  const frHigherRows = useMemo(() => payload?.fr_higher_comparables ?? [], [payload]);
  const frOnlyRows = useMemo(() => payload?.fr_only_comparables ?? [], [payload]);
  const fdOnlyRows = useMemo(() => payload?.fd_only_comparables ?? [], [payload]);
  const matchProgress = useMemo(() => payload?.match_progress ?? [], [payload]);
  const filteredProgress = useMemo(() => {
    const needle = progressSearch.trim().toLowerCase();
    if (!needle) {
      return matchProgress;
    }
    return matchProgress.filter((row) => row.match.toLowerCase().includes(needle));
  }, [matchProgress, progressSearch]);

  const overlapHint = useMemo(() => {
    if ((payload?.comparable_count ?? 0) > 0) {
      return "";
    }
    const fdEvents = payload?.fd_event_count ?? 0;
    const frEvents = payload?.fr_event_count ?? 0;
    if (fdEvents === 0 && (payload?.fr_only_count ?? 0) > 0) {
      return "Des props joueuses existent cote FR, mais FanDuel ne les propose pas sur ces matchs.";
    }
    if (fdEvents > 0 && frEvents === 0) {
      return "FanDuel propose des props WNBA, mais les books FR n'ont pas de lignes comparables.";
    }
    if (fdEvents > 0 && frEvents > 0) {
      return "FR et FanDuel ont des props, mais pas sur les memes matchs ou pas aux memes seuils.";
    }
    return "";
  }, [payload]);

  return (
    <>
      <header className="hero">
        <p className="eyebrow">Basket WNBA</p>
        <h1>Props joueuses — books FR vs FanDuel</h1>
        <p className="lead">
          Compare les stats joueuses <strong>points, rebonds, assists, 3pts, combos, paliers</strong>{" "}
          (Unibet, Betclic, Winamax) avec FanDuel.
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
            placeholder="dream, lynx, gray..."
          />
        </label>
        <button type="button" onClick={onSubmit} disabled={busy}>
          {busy ? "Comparaison WNBA..." : "Lancer comparaison WNBA"}
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
          <span className="meta-label">Matchs</span>
          <strong>
            {payload?.matches_done ?? status?.matches_done ?? 0}
            {payload?.anchors_total || status?.anchors_total
              ? ` / ${payload?.anchors_total ?? status?.anchors_total}`
              : ""}
          </strong>
        </div>
        <div>
          <span className="meta-label">Lignes comparees</span>
          <strong>{payload?.comparable_count ?? 0}</strong>
        </div>
        <div>
          <span className="meta-label">FR paie mieux</span>
          <strong>{payload?.fr_higher_count ?? 0}</strong>
        </div>
        <div>
          <span className="meta-label">FR sans FD</span>
          <strong>{payload?.fr_only_count ?? 0}</strong>
        </div>
        <div>
          <span className="meta-label">FD sans FR</span>
          <strong>{payload?.fd_only_count ?? 0}</strong>
        </div>
      </section>

      {overlapHint ? (
        <section className="panel">
          <p className="hint">{overlapHint}</p>
        </section>
      ) : null}

      {matchProgress.length > 0 ? (
        <CollapsibleSection
          title="Avancement par match"
          badge={filteredProgress.length}
          defaultOpen={false}
          search={{
            value: progressSearch,
            onChange: setProgressSearch,
            placeholder: "Filtrer par equipe ou match...",
          }}
        >
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Match</th>
                  <th>Comparees</th>
                  <th>Lignes FR</th>
                  <th>Lignes FD</th>
                  <th>FR seul</th>
                  <th>FD seul</th>
                  <th>FanDuel</th>
                </tr>
              </thead>
              <tbody>
                {filteredProgress.map((row) => (
                  <tr key={row.match}>
                    <td data-label="Match">{row.match}</td>
                    <td data-label="Comparees">{row.comparable_count}</td>
                    <td data-label="Lignes FR">
                      {row.fr_market_count ?? row.fr_ace_market_count ?? 0}
                    </td>
                    <td data-label="Lignes FD">
                      {row.fd_market_count ?? row.fd_ace_market_count ?? 0}
                    </td>
                    <td data-label="FR seul">{row.fr_only_count}</td>
                    <td data-label="FD seul">{row.fd_only_count ?? 0}</td>
                    <td data-label="FanDuel">{row.fanduel_found ? "oui" : "non"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CollapsibleSection>
      ) : null}

      <ResultsTable
        title="Toutes les props comparees"
        rows={payload?.comparables ?? []}
        marketKind="wnba"
        emptyMessage="Aucun resultat WNBA. Lance une comparaison."
      />

      <ResultsTable
        title="Lignes ou le book FR paie mieux que FanDuel"
        rows={frHigherRows}
        marketKind="wnba"
        emptyMessage="Aucune ligne ou la cote FR bat FanDuel sur ce run."
      />

      <CollapsibleSection
        title="Props FR sans equivalent FanDuel (meme seuil)"
        badge={frOnlyRows.length}
        defaultOpen={false}
        search={{
          value: frOnlySearch,
          onChange: setFrOnlySearch,
          placeholder: "Match, joueuse, book...",
        }}
      >
        <ResultsTable
          title=""
          rows={frOnlyRows}
          marketKind="wnba"
          searchQuery={frOnlySearch}
          embedded
          emptyMessage="Toutes les lignes FR ont un equivalent FanDuel, ou pas de prop FR."
        />
      </CollapsibleSection>

      <CollapsibleSection
        title="Props FanDuel sans equivalent FR (meme seuil)"
        badge={fdOnlyRows.length}
        defaultOpen={false}
        search={{
          value: fdOnlySearch,
          onChange: setFdOnlySearch,
          placeholder: "Match, marche FanDuel...",
        }}
      >
        <ResultsTable
          title=""
          rows={fdOnlyRows}
          marketKind="wnba"
          searchQuery={fdOnlySearch}
          embedded
          emptyMessage="Toutes les lignes FanDuel ont un equivalent FR, ou pas de prop FanDuel."
        />
      </CollapsibleSection>
    </>
  );
}
