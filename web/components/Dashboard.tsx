"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { CollapsibleSection } from "@/components/CollapsibleSection";
import { ResultsTable } from "@/components/ResultsTable";
import { RunningBanner } from "@/components/RunningBanner";
import { ValuesTable } from "@/components/ValuesTable";
import { buildValueRows } from "@/lib/mptoValue";
import type { ApiPayload, RunStatus, TennisMarketKind } from "@/lib/types";
import { isCombinedPayload, pickMarketPayload, getPayloadProgressSnapshot } from "@/lib/types";
import { isPayloadFromRun, resolveRunStartedAt } from "@/lib/runSession";
import {
  hasTennisData,
  loadCachedTennisResults,
  saveCachedTennisResults,
} from "@/lib/tennisCache";

const SECRET_STORAGE_KEY = "aces_trigger_secret";
const ALL_TENNIS_MARKETS: TennisMarketKind[] = ["aces", "breaks", "victoires"];

const SECTION_IDS = ["progress", "comparables", "frHigher", "values", "frOnly", "fdOnly"] as const;
type SectionId = (typeof SECTION_IDS)[number];

function defaultOpenSections(): Record<SectionId, boolean> {
  return {
    progress: false,
    comparables: true,
    frHigher: true,
    values: true,
    frOnly: false,
    fdOnly: false,
  };
}

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

function emptyTennisPayload(): ApiPayload {
  return {
    source: "tennis_aces_comparable",
    generated_at: "",
    partial: true,
    comparable_count: 0,
    fr_higher_count: 0,
    comparables: [],
    fr_higher_comparables: [],
  };
}

function marketsQuery(selected: Record<TennisMarketKind, boolean>): string {
  const active = ALL_TENNIS_MARKETS.filter((key) => selected[key]);
  if (active.length === 0 || active.length === ALL_TENNIS_MARKETS.length) {
    return "";
  }
  return active.join(",");
}

export function Dashboard({ embedded = false }: { embedded?: boolean }) {
  const [secret, setSecret] = useState("");
  const [match, setMatch] = useState("");
  const [selectedMarkets, setSelectedMarkets] = useState<Record<TennisMarketKind, boolean>>({
    aces: true,
    breaks: true,
    victoires: true,
  });
  const [marketTab, setMarketTab] = useState<TennisMarketKind>("aces");
  const [progressSearch, setProgressSearch] = useState("");
  const [comparablesSearch, setComparablesSearch] = useState("");
  const [frHigherSearch, setFrHigherSearch] = useState("");
  const [valuesSearch, setValuesSearch] = useState("");
  const [frOnlySearch, setFrOnlySearch] = useState("");
  const [fdOnlySearch, setFdOnlySearch] = useState("");
  const [openSections, setOpenSections] = useState<Record<SectionId, boolean>>(defaultOpenSections);
  const [rawPayload, setRawPayload] = useState<ApiPayload | null>(null);
  const [status, setStatus] = useState<RunStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const suppressCacheRef = useRef(false);
  const runStartedAtRef = useRef<string | null>(null);
  const runAbortRef = useRef<AbortController | null>(null);
  const [cancelBusy, setCancelBusy] = useState(false);

  const isRunning = busy || status?.status === "running";

  useEffect(() => {
    const saved = window.localStorage.getItem(SECRET_STORAGE_KEY);
    if (saved) {
      setSecret(saved);
    }
    const cached = loadCachedTennisResults();
    if (cached) {
      setRawPayload(cached.payload);
      setStatus(cached.status);
    }
  }, []);

  const refresh = useCallback(async () => {
    const response = await fetch("/api/results", { cache: "no-store" });
    if (!response.ok) {
      throw new Error("Impossible de charger les resultats.");
    }
    const data = await response.json();
    const nextPayload = (data.payload as ApiPayload) ?? null;
    const nextStatus = (data.status as RunStatus) ?? null;
    const runStartedAt = resolveRunStartedAt(runStartedAtRef.current, nextStatus);
    const payloadFromCurrentRun =
      nextPayload &&
      hasTennisData(nextPayload) &&
      isPayloadFromRun(nextPayload, runStartedAt);

    if (payloadFromCurrentRun) {
      setRawPayload(nextPayload);
      // Toujours persister, meme pendant un run (sinon fermer l'app = resultats perdus).
      saveCachedTennisResults(nextPayload, nextStatus);
    } else if (data.source === "runner-unreachable") {
      // Ne pas vider l'ecran pendant un run — juste retomber sur le cache si dispo.
      const cached = loadCachedTennisResults();
      if (cached) {
        setRawPayload(cached.payload);
        if (!status || status.status !== "running") {
          setStatus(cached.status);
        }
      }
    } else if (
      nextPayload &&
      hasTennisData(nextPayload) &&
      !runStartedAtRef.current &&
      !suppressCacheRef.current
    ) {
      // Reouverture: reprendre les derniers resultats runner s'ils existent.
      setRawPayload(nextPayload);
      saveCachedTennisResults(nextPayload, nextStatus);
    }

    if (
      nextStatus &&
      !suppressCacheRef.current &&
      data.source !== "runner-unreachable"
    ) {
      setStatus(nextStatus);
    } else if (nextStatus && suppressCacheRef.current && data.source !== "runner-unreachable") {
      setStatus(nextStatus);
    }

    return data as {
      payload: ApiPayload | null;
      status: RunStatus | null;
      source?: string;
    };
  }, []);

  useEffect(() => {
    refresh().catch((exc) => setError(exc instanceof Error ? exc.message : "Erreur inconnue."));
  }, [refresh]);

  useEffect(() => {
    if (!isRunning) {
      return;
    }
    const timer = window.setInterval(() => {
      refresh().catch(() => undefined);
    }, 500);
    return () => window.clearInterval(timer);
  }, [isRunning, refresh]);

  const waitForCompletion = useCallback(
    async (signal?: AbortSignal) => {
      // Tant que le runner dit "running", on continue (aligne sur timeout runner ~45 min).
      const hardDeadline = Date.now() + 50 * 60 * 1000;
      let lastRows = 0;
      let lastMatches = 0;
      let unreachableStreak = 0;

      while (Date.now() < hardDeadline) {
        if (signal?.aborted) {
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, 500));
        if (signal?.aborted) {
          return;
        }
        const data = await refresh();
        const progress = getPayloadProgressSnapshot(data.payload);
        const currentStatus = data.status?.status;
        const comparableCount = progress.comparable_count;
        const frOnlyCount = progress.fr_only_count;
        const totalRows = comparableCount + frOnlyCount;
        const matchesDone = data.status?.matches_done ?? progress.matches_done;
        const anchorsTotal = data.status?.anchors_total ?? progress.anchors_total;
        const isFinalPayload = progress.partial === false;

        if (data.source === "runner-unreachable") {
          unreachableStreak += 1;
          if (unreachableStreak === 1 || unreachableStreak % 20 === 0) {
            setInfo(
              "Connexion runner instable — le scrape EU continue; resultats partiels conserves.",
            );
            setError("");
          }
          continue;
        }
        if (unreachableStreak > 0) {
          unreachableStreak = 0;
          setError("");
          setInfo("Connexion runner retablie — reprise du suivi...");
        }

        if (matchesDone > lastMatches || totalRows > lastRows) {
          lastMatches = matchesDone;
          lastRows = totalRows;
          if (anchorsTotal > 0) {
            setInfo(
              `${matchesDone}/${anchorsTotal} match(s) — ${totalRows} ligne(s) affichee(s)...`,
            );
          } else {
            setInfo(`${totalRows} ligne(s) affichee(s), comparaison en cours...`);
          }
        } else if (currentStatus === "running") {
          setInfo(data.status?.message || "Comparaison en cours...");
        }

        if (currentStatus === "cancelled") {
          setInfo("Comparaison annulee.");
          return;
        }

        if (currentStatus === "error") {
          if (totalRows > 0 || matchesDone > 0) {
            setInfo(
              `${matchesDone}/${anchorsTotal || "?"} match(s), ${totalRows} ligne(s) (partiel).`,
            );
            return;
          }
          throw new Error(data.status?.message || "La comparaison a echoue.");
        }

        if (currentStatus === "success" || isFinalPayload) {
          return;
        }
      }

      if (signal?.aborted) {
        return;
      }

      const finalData = await refresh();
      const finalProgress = getPayloadProgressSnapshot(finalData.payload);
      const finalRows = finalProgress.comparable_count + finalProgress.fr_only_count;
      const finalMatches =
        finalData.status?.matches_done ?? finalProgress.matches_done;
      if (finalData.status?.status === "running") {
        setInfo(
          `${finalMatches} match(s), ${finalRows} ligne(s) — le runner continue encore. Recharge ou reclique "Lancer" pour reprendre le suivi (sans perdre la progression EU).`,
        );
        return;
      }
      if (finalRows > 0 || finalMatches > 0) {
        setInfo(`${finalRows} ligne(s) affichees (delai max atteint).`);
        return;
      }
      throw new Error("Delai depasse (~20 min). Recharge la page.");
    },
    [refresh],
  );

  const onCancel = async () => {
    if (!secret.trim()) {
      setError("Saisis ton code secret pour arreter la comparaison.");
      return;
    }
    setCancelBusy(true);
    runAbortRef.current?.abort();
    try {
      const response = await fetch("/api/cancel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ secret: secret.trim(), sport: "tennis" }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(data.error || "Impossible d'arreter la comparaison.");
      } else {
        setInfo(data.message || "Comparaison arretee.");
        setStatus({
          status: "cancelled",
          message: "Comparaison annulee par l'utilisateur.",
        });
      }
      await refresh();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Erreur lors de l'arret.");
    } finally {
      suppressCacheRef.current = false;
      setBusy(false);
      setCancelBusy(false);
      runStartedAtRef.current = null;
    }
  };

  const onSubmit = async () => {
    setError("");
    setInfo("");
    if (!secret.trim()) {
      setError("Saisis ton code secret.");
      return;
    }

    window.localStorage.setItem(SECRET_STORAGE_KEY, secret.trim());
    setBusy(true);
    runAbortRef.current = new AbortController();
    const runSignal = runAbortRef.current.signal;

    try {
      const markets = marketsQuery(selectedMarkets);
      const response = await fetch("/api/trigger", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          secret: secret.trim(),
          match: match.trim(),
          sport: "tennis",
          ...(markets ? { markets } : {}),
        }),
      });
      const data = await response.json();

      if (response.status === 409 && data.already_running) {
        // Une compare EU tourne deja : on reprend le suivi sans tout effacer.
        suppressCacheRef.current = true;
        if (typeof data.started_at === "string" && data.started_at.trim()) {
          runStartedAtRef.current = data.started_at.trim();
        }
        setStatus({
          status: "running",
          message: data.message || "Comparaison deja en cours...",
          matches_done: data.matches_done,
          anchors_total: data.anchors_total,
        });
        setInfo(
          `Comparaison deja active (${data.matches_done ?? 0}/${data.anchors_total ?? "?"}) — reprise du suivi sans reset.`,
        );
        await waitForCompletion(runSignal);
        if (!runSignal.aborted) {
          await refresh();
          setInfo("Comparaison terminee.");
        }
        return;
      }

      if (!response.ok) {
        throw new Error(data.error || "Echec du declenchement.");
      }

      // Ne pas effacer le cache: on ecrase au fil de l'eau. Fermer l'app ne perd plus les resultats.
      suppressCacheRef.current = true;
      runStartedAtRef.current =
        typeof data.started_at === "string" && data.started_at.trim()
          ? data.started_at.trim()
          : new Date().toISOString();
      setStatus({ status: "running", message: "Comparaison tennis en cours..." });
      setInfo("Scrape live en cours...");
      await waitForCompletion(runSignal);
      if (runSignal.aborted) {
        return;
      }
      await refresh();
      setInfo("Comparaison terminee.");
    } catch (exc) {
      if (!runSignal.aborted) {
        setError(exc instanceof Error ? exc.message : "Erreur inconnue.");
      }
    } finally {
      if (!runSignal.aborted) {
        suppressCacheRef.current = false;
        setBusy(false);
      }
      runStartedAtRef.current = null;
      runAbortRef.current = null;
    }
  };

  const acesPayload = useMemo(
    () => pickMarketPayload(rawPayload, "aces"),
    [rawPayload],
  );
  const breaksPayload = useMemo(
    () => pickMarketPayload(rawPayload, "breaks"),
    [rawPayload],
  );
  const victoiresPayload = useMemo(
    () => pickMarketPayload(rawPayload, "victoires"),
    [rawPayload],
  );
  const payload = useMemo(() => {
    if (marketTab === "aces") {
      return acesPayload;
    }
    if (marketTab === "breaks") {
      return breaksPayload;
    }
    return victoiresPayload;
  }, [marketTab, acesPayload, breaksPayload, victoiresPayload]);
  const combined = useMemo(() => isCombinedPayload(rawPayload), [rawPayload]);
  const rootMeta = rawPayload;

  const frHigherRows = useMemo(
    () => payload?.fr_higher_comparables ?? [],
    [payload],
  );
  const valueRows = useMemo(
    () => buildValueRows(frHigherRows, marketTab),
    [frHigherRows, marketTab],
  );
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
    const label =
      marketTab === "breaks"
        ? "breaks / tie-breaks"
        : marketTab === "victoires"
          ? "victoires (moneyline)"
          : "aces";
    const fdEvents = payload?.fd_event_count ?? payload?.fd_ace_event_count ?? 0;
    const frEvents = payload?.fr_event_count ?? payload?.fr_ace_event_count ?? 0;
    if (marketTab === "aces" && fdEvents === 0 && (payload?.fr_only_count ?? 0) > 0) {
      return "FanDuel ne propose aucun marche aces sur le calendrier actuel. Les lignes FR restent visibles en « FR seul » jusqu'a ce qu'un match ait des aces FD (ex. tableau principal ATP/WTA). Beaucoup de matchs (challengers) n'ont tout simplement pas d'aces cote books.";
    }
    if (marketTab === "aces" && fdEvents <= 5 && (payload?.anchors_total ?? 0) > 50) {
      return "Peu de matchs ont des props aces (souvent 5–15 sur 100+). Les autres n'ont ni FR ni FanDuel aces — ce n'est pas un plantage du scrape. Les lignes comparees n'apparaissent que quand les deux bords ont le meme seuil.";
    }
    if (marketTab === "breaks" && fdEvents > 0 && frEvents === 0) {
      return "FanDuel propose des tie-breaks O/U ou premier break, mais les books FR n'ont pas le même marché ce soir (ex. seulement tie-break par set, ou FD sans ligne 0,5).";
    }
    if (marketTab === "victoires" && fdEvents === 0 && (payload?.fr_only_count ?? 0) > 0) {
      return "FanDuel n'a pas de moneyline alignee sur ces matchs FR — les vainqueurs restent en « FR seul ».";
    }
    if (marketTab === "victoires" && (payload?.comparable_count ?? 0) > 0) {
      return "Cotes = snapshot au moment du scrape de chaque match (un run long peut avoir des live deja bougees). Relance pour rafraichir.";
    }
    if (fdEvents > 0 && frEvents === 0) {
      return `FanDuel propose des ${label}, mais les books FR n'ont pas de lignes comparables sur ces matchs.`;
    }
    if (fdEvents === 0 && frEvents > 0) {
      return `Des lignes ${label} existent cote FR, mais FanDuel ne les propose pas sur ces matchs.`;
    }
    if (fdEvents > 0 && frEvents > 0) {
      return `FR et FanDuel ont des ${label}, mais pas sur les memes matchs ou pas aux memes seuils.`;
    }
    return "";
  }, [payload, marketTab]);

  const setSectionOpen = (id: SectionId, open: boolean) => {
    setOpenSections((current) => ({ ...current, [id]: open }));
  };

  const collapseAllSections = () => {
    setOpenSections({
      progress: false,
      comparables: false,
      frHigher: false,
      values: false,
      frOnly: false,
      fdOnly: false,
    });
  };

  const expandAllSections = () => {
    setOpenSections({
      progress: true,
      comparables: true,
      frHigher: true,
      values: true,
      frOnly: true,
      fdOnly: true,
    });
  };

  const allCollapsed = SECTION_IDS.every((id) => !openSections[id]);

  const content = (
    <>
      <header className="hero">
        <p className="eyebrow">Tennis props</p>
        <h1>Aces, breaks & victoires — books FR vs FanDuel</h1>
        <p className="lead">
          Compare les lignes <strong>aces</strong>, <strong>breaks</strong> et{" "}
          <strong>victoires</strong> (Unibet, Betclic, Winamax) avec FanDuel — prematch et matchs en
          cours.
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
        <fieldset className="market-select" disabled={busy}>
          <legend>Marches a comparer</legend>
          {(
            [
              ["aces", "Aces"],
              ["breaks", "Breaks"],
              ["victoires", "Victoires"],
            ] as const
          ).map(([key, label]) => (
            <label key={key} className="market-check">
              <input
                type="checkbox"
                checked={selectedMarkets[key]}
                onChange={(event) => {
                  const checked = event.target.checked;
                  setSelectedMarkets((current) => {
                    const next = { ...current, [key]: checked };
                    if (!ALL_TENNIS_MARKETS.some((market) => next[market])) {
                      return current;
                    }
                    return next;
                  });
                }}
              />
              {label}
            </label>
          ))}
          <p className="hint">Tout coche = tous les marches (defaut).</p>
        </fieldset>
        <button type="button" onClick={onSubmit} disabled={busy}>
          {busy ? "Comparaison en cours..." : "Lancer comparaison"}
        </button>
        {info ? <p className="info">{info}</p> : null}
        {error ? <p className="error">{error}</p> : null}
      </section>

      <RunningBanner
        active={isRunning}
        label="Comparaison tennis en cours"
        message={status?.message || info || "Scrape live en cours — les anciens resultats ont ete effaces."}
        onCancel={onCancel}
        cancelBusy={cancelBusy}
      />

      <div className="market-tabs">
        <button
          type="button"
          className={`market-tab${marketTab === "aces" ? " active" : ""}`}
          onClick={() => setMarketTab("aces")}
        >
          Aces
          {combined ? ` (${acesPayload?.comparable_count ?? 0})` : ""}
        </button>
        <button
          type="button"
          className={`market-tab${marketTab === "breaks" ? " active" : ""}`}
          onClick={() => setMarketTab("breaks")}
          disabled={!combined}
          title={combined ? "" : "Breaks disponibles apres redeploiement runner"}
        >
          Breaks
          {combined ? ` (${breaksPayload?.comparable_count ?? 0})` : ""}
        </button>
        <button
          type="button"
          className={`market-tab${marketTab === "victoires" ? " active" : ""}`}
          onClick={() => setMarketTab("victoires")}
          disabled={!combined || !victoiresPayload}
          title={
            combined && victoiresPayload
              ? ""
              : "Victoires disponibles apres redeploiement runner"
          }
        >
          Victoires
          {combined && victoiresPayload ? ` (${victoiresPayload.comparable_count ?? 0})` : ""}
        </button>
        <button
          type="button"
          className="ghost-btn sections-toggle"
          onClick={allCollapsed ? expandAllSections : collapseAllSections}
        >
          {allCollapsed ? "Tout deplier" : "Tout replier"}
        </button>
      </div>

      <section className="panel meta">
        <div>
          <span className="meta-label">Derniere mise a jour</span>
          <strong>{formatTimestamp(rootMeta?.generated_at)}</strong>
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
          <span className="meta-label" title="Matchs deja compares sur le total decouvert">
            Matchs
          </span>
          <strong>
            {payload?.matches_done ?? status?.matches_done ?? 0}
            {payload?.anchors_total || status?.anchors_total
              ? ` / ${payload?.anchors_total ?? status?.anchors_total}`
              : ""}
          </strong>
        </div>
        <div>
          <span className="meta-label" title="Lignes alignees entre un book FR et FanDuel">
            Lignes comparees ({marketTab})
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
          <span className="meta-label" title="Values MPTO positives (Kelly 0,25) sur lignes FR > FD">
            Values MPTO
          </span>
          <strong>{valueRows.length}</strong>
        </div>
        <div>
          <span className="meta-label" title="Lignes FR sans equivalent FanDuel sur la meme ligne">
            FR sans FD
          </span>
          <strong>{payload?.fr_only_count ?? 0}</strong>
        </div>
        <div>
          <span className="meta-label" title="Lignes FanDuel sans equivalent FR sur la meme ligne">
            FD sans FR
          </span>
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
          open={openSections.progress}
          onOpenChange={(open) => setSectionOpen("progress", open)}
          search={{
            value: progressSearch,
            onChange: setProgressSearch,
            placeholder: "Filtrer par joueur ou match...",
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
                    <td data-label="FanDuel">
                      {row.skipped
                        ? `skip${row.skip_reason ? ` (${row.skip_reason})` : ""}`
                        : row.fanduel_found
                          ? "oui"
                          : "non"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CollapsibleSection>
      ) : null}

      <CollapsibleSection
        title={`Toutes les lignes ${marketTab} comparees`}
        badge={payload?.comparables?.length ?? 0}
        open={openSections.comparables}
        onOpenChange={(open) => setSectionOpen("comparables", open)}
        search={{
          value: comparablesSearch,
          onChange: setComparablesSearch,
          placeholder: "Match, book, ligne...",
        }}
      >
        <ResultsTable
          title=""
          rows={payload?.comparables ?? []}
          marketKind={marketTab}
          searchQuery={comparablesSearch}
          embedded
          showCaptureDetails
          runGeneratedAt={payload?.generated_at ?? rootMeta?.generated_at}
          emptyMessage="Aucun resultat pour le moment. Lance une comparaison."
        />
      </CollapsibleSection>

      <CollapsibleSection
        title="Lignes ou le book FR paie mieux que FanDuel"
        badge={frHigherRows.length}
        open={openSections.frHigher}
        onOpenChange={(open) => setSectionOpen("frHigher", open)}
        search={{
          value: frHigherSearch,
          onChange: setFrHigherSearch,
          placeholder: "Match, book, ligne...",
        }}
      >
        <ResultsTable
          title=""
          rows={frHigherRows}
          marketKind={marketTab}
          searchQuery={frHigherSearch}
          embedded
          showCaptureDetails
          runGeneratedAt={payload?.generated_at ?? rootMeta?.generated_at}
          emptyMessage="Aucune ligne ou la cote FR bat FanDuel sur ce run."
        />
      </CollapsibleSection>

      <CollapsibleSection
        title="Values MPTO — book FR vs FanDuel"
        badge={valueRows.length}
        open={openSections.values}
        onOpenChange={(open) => setSectionOpen("values", open)}
        search={{
          value: valuesSearch,
          onChange: setValuesSearch,
          placeholder: "Match, pari, book...",
        }}
      >
        <ValuesTable
          title=""
          rows={valueRows}
          searchQuery={valuesSearch}
          embedded
          showCaptureDetails
          runGeneratedAt={payload?.generated_at ?? rootMeta?.generated_at}
          emptyMessage="Aucune value MPTO positive (Kelly 0,25) sur les lignes ou le FR paie mieux que FD."
        />
      </CollapsibleSection>

      <CollapsibleSection
        title={`Lignes ${marketTab} FR sans equivalent FanDuel (meme seuil)`}
        badge={frOnlyRows.length}
        open={openSections.frOnly}
        onOpenChange={(open) => setSectionOpen("frOnly", open)}
        search={{
          value: frOnlySearch,
          onChange: setFrOnlySearch,
          placeholder: "Match, book, ligne...",
        }}
      >
        <ResultsTable
          title=""
          rows={frOnlyRows}
          marketKind={marketTab}
          searchQuery={frOnlySearch}
          embedded
          showCaptureDetails
          runGeneratedAt={payload?.generated_at ?? rootMeta?.generated_at}
          emptyMessage={`Toutes les lignes FR ont un equivalent FanDuel, ou pas de marche ${marketTab} FR.`}
        />
      </CollapsibleSection>

      <CollapsibleSection
        title={`Lignes ${marketTab} FanDuel sans equivalent FR (meme seuil)`}
        badge={fdOnlyRows.length}
        open={openSections.fdOnly}
        onOpenChange={(open) => setSectionOpen("fdOnly", open)}
        search={{
          value: fdOnlySearch,
          onChange: setFdOnlySearch,
          placeholder: "Match, marche FanDuel...",
        }}
      >
        <ResultsTable
          title=""
          rows={fdOnlyRows}
          marketKind={marketTab}
          searchQuery={fdOnlySearch}
          embedded
          showCaptureDetails
          runGeneratedAt={payload?.generated_at ?? rootMeta?.generated_at}
          emptyMessage={`Toutes les lignes FanDuel ont un equivalent FR, ou pas de marche ${marketTab} FanDuel.`}
        />
      </CollapsibleSection>
    </>
  );

  if (embedded) {
    return content;
  }

  return <main className="page">{content}</main>;
}
