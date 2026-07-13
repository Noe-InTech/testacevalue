"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { CollapsibleSection } from "@/components/CollapsibleSection";
import { ResultsTable } from "@/components/ResultsTable";
import { RunningBanner } from "@/components/RunningBanner";
import type { MarketPayload, RunStatus } from "@/lib/types";
import { getPayloadProgressSnapshot } from "@/lib/types";
import { isPayloadFromRun, resolveRunStartedAt } from "@/lib/runSession";
import {
  clearCachedWnbaResults,
  countRowsByStat,
  filterWnbaRows,
  hasWnbaData,
  loadCachedWnbaResults,
  saveCachedWnbaResults,
  WNBA_BOOK_FILTERS,
  WNBA_STAT_FILTERS,
  type WnbaBookFilter,
} from "@/lib/wnba";
import {
  clearCachedNbaResults,
  filterNbaRows,
  hasNbaData,
  loadCachedNbaResults,
  NBA_BOOK_FILTERS,
  NBA_STAT_FILTERS,
  saveCachedNbaResults,
  type NbaBookFilter,
} from "@/lib/nba";

type BasketballLeague = "wnba" | "nba";
type BookFilter = WnbaBookFilter | NbaBookFilter;

function leagueConfig(league: BasketballLeague) {
  if (league === "nba") {
    return {
      label: "NBA",
      apiSport: "nba" as const,
      marketKind: "nba" as const,
      source: "nba_player_props_comparable",
      hasData: hasNbaData,
      loadCache: loadCachedNbaResults,
      saveCache: saveCachedNbaResults,
      clearCache: clearCachedNbaResults,
      statFilters: NBA_STAT_FILTERS,
      bookFilters: NBA_BOOK_FILTERS,
      filterRows: filterNbaRows,
    };
  }
  return {
    label: "WNBA",
    apiSport: "wnba" as const,
    marketKind: "wnba" as const,
    source: "wnba_player_props_comparable",
    hasData: hasWnbaData,
    loadCache: loadCachedWnbaResults,
    saveCache: saveCachedWnbaResults,
    clearCache: clearCachedWnbaResults,
    statFilters: WNBA_STAT_FILTERS,
    bookFilters: WNBA_BOOK_FILTERS,
    filterRows: filterWnbaRows,
  };
}

function emptyBasketballPayload(source: string): MarketPayload {
  return {
    source,
    generated_at: "",
    partial: true,
    comparable_count: 0,
    fr_higher_count: 0,
    comparables: [],
    fr_higher_comparables: [],
    fr_only_comparables: [],
    fd_only_comparables: [],
    match_progress: [],
  };
}

const SECRET_STORAGE_KEY = "aces_trigger_secret";
const SECTION_IDS = ["progress", "comparables", "frHigher", "frOnly", "fdOnly"] as const;
type SectionId = (typeof SECTION_IDS)[number];

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

function defaultOpenSections(): Record<SectionId, boolean> {
  return {
    progress: false,
    comparables: true,
    frHigher: true,
    frOnly: false,
    fdOnly: false,
  };
}

export function BasketballDashboard({ league = "wnba" }: { league?: BasketballLeague }) {
  const cfg = leagueConfig(league);
  const [secret, setSecret] = useState("");
  const [match, setMatch] = useState("");
  const [globalSearch, setGlobalSearch] = useState("");
  const [displayMatchFilter, setDisplayMatchFilter] = useState("");
  const [statFilter, setStatFilter] = useState("all");
  const [bookFilter, setBookFilter] = useState<BookFilter>("Tous");
  const [progressSearch, setProgressSearch] = useState("");
  const [openSections, setOpenSections] = useState<Record<SectionId, boolean>>(defaultOpenSections);
  const [payload, setPayload] = useState<MarketPayload | null>(null);
  const [status, setStatus] = useState<RunStatus | null>(null);
  const [cacheSavedAt, setCacheSavedAt] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [warning, setWarning] = useState("");
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
    const cached = cfg.loadCache();
    if (cached) {
      setPayload(cached.payload);
      setStatus(cached.status);
      setCacheSavedAt(cached.savedAt);
    }
  }, []);

  const applyResults = useCallback((nextPayload: MarketPayload | null, nextStatus: RunStatus | null) => {
    if (nextPayload && cfg.hasData(nextPayload)) {
      setPayload(nextPayload);
      cfg.saveCache(nextPayload, nextStatus);
      setCacheSavedAt(new Date().toISOString());
    }
    if (nextStatus) {
      setStatus(nextStatus);
    }
  }, [cfg]);

  const refresh = useCallback(
    async (options?: { silent?: boolean }) => {
      try {
        const response = await fetch(`/api/results?sport=${cfg.apiSport}`, { cache: "no-store" });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        const nextPayload = (data.payload as MarketPayload) ?? null;
        const nextStatus = (data.status as RunStatus) ?? null;
        const runStartedAt = resolveRunStartedAt(runStartedAtRef.current, nextStatus);
        const payloadFromCurrentRun =
          nextPayload &&
          cfg.hasData(nextPayload) &&
          isPayloadFromRun(nextPayload, runStartedAt);

        if (payloadFromCurrentRun) {
          applyResults(nextPayload, nextStatus);
          if (!options?.silent) {
            setWarning("");
          }
        } else if (
          nextStatus?.status === "success" &&
          nextPayload &&
          cfg.hasData(nextPayload) &&
          data.source === "runner-live"
        ) {
          applyResults(nextPayload, nextStatus);
          if (!options?.silent) {
            setWarning("");
          }
        } else if (suppressCacheRef.current) {
          setPayload(emptyBasketballPayload(cfg.source));
          setCacheSavedAt(null);
          if (nextStatus) {
            setStatus(nextStatus);
          }
        } else if (data.source === "runner-unreachable") {
          if (!suppressCacheRef.current) {
            const cached = cfg.loadCache();
            if (cached) {
              setPayload(cached.payload);
              setStatus(cached.status);
              setCacheSavedAt(cached.savedAt);
              setWarning(
                "Runner EU injoignable — derniers resultats en memoire affiches. Mets a jour RUNNER_URL sur Vercel.",
              );
            } else if (!options?.silent) {
              setWarning(
                "Runner EU injoignable. Mets a jour RUNNER_URL (URL Cloudflare https://....trycloudflare.com).",
              );
            }
          }
        } else if (nextStatus && !suppressCacheRef.current) {
          setStatus(nextStatus);
        }

        return data as {
          payload: MarketPayload | null;
          status: RunStatus | null;
          source?: string;
        };
      } catch (exc) {
        if (!suppressCacheRef.current) {
          const cached = cfg.loadCache();
          if (cached) {
            setPayload(cached.payload);
            setStatus(cached.status);
            setCacheSavedAt(cached.savedAt);
            setWarning(
              exc instanceof Error
                ? `Connexion instable (${exc.message}) — derniers resultats en memoire.`
                : "Connexion instable — derniers resultats en memoire.",
            );
            return {
              payload: cached.payload,
              status: cached.status,
              source: "cache",
            };
          }
        }
        if (!options?.silent) {
          throw exc;
        }
        return {
          payload: null,
          status: null,
          source: "error",
        };
      }
    },
    [applyResults, cfg],
  );

  useEffect(() => {
    refresh({ silent: true }).catch((exc) => {
      if (!cfg.loadCache()) {
        setError(exc instanceof Error ? exc.message : `Impossible de charger les resultats ${cfg.label}.`);
      }
    });
  }, [refresh]);

  useEffect(() => {
    if (!isRunning) {
      return;
    }
    const timer = window.setInterval(() => {
      refresh({ silent: true }).catch(() => undefined);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [isRunning, refresh]);

  const waitForCompletion = useCallback(async (signal?: AbortSignal) => {
    const deadline = Date.now() + 8 * 60 * 1000;
    let lastRows = 0;
    let lastMatches = 0;

    while (Date.now() < deadline) {
      if (signal?.aborted) {
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 500));
      if (signal?.aborted) {
        return;
      }
      const data = await refresh({ silent: true });
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
        setInfo(data.status?.message || `Comparaison ${cfg.label} en cours...`);
      }

      if (data.source === "runner-unreachable" && !cfg.hasData(data.payload) && !cfg.loadCache()) {
        throw new Error(
          "Runner EU injoignable. Mets a jour RUNNER_URL sur Vercel (URL Cloudflare).",
        );
      }

      if (currentStatus === "cancelled") {
        setInfo(`Comparaison ${cfg.label} annulee.`);
        return;
      }

      if (currentStatus === "error") {
        if (totalRows > 0 || matchesDone > 0 || cfg.loadCache()) {
          setInfo(`${matchesDone}/${anchorsTotal || "?"} match(s), ${totalRows} ligne(s) (partiel).`);
          return;
        }
        throw new Error(data.status?.message || `La comparaison ${cfg.label} a echoue.`);
      }

      if (currentStatus === "success" || isFinalPayload) {
        return;
      }
    }

    if (signal?.aborted) {
      return;
    }

    const finalData = await refresh({ silent: true });
    const finalProgress = getPayloadProgressSnapshot(finalData.payload);
    const finalRows = finalProgress.comparable_count + finalProgress.fr_only_count;
    if (finalRows > 0 || (finalData.status?.matches_done ?? finalProgress.matches_done) > 0) {
      setInfo(`${finalRows} ligne(s) affichees (delai max atteint).`);
      return;
    }
    throw new Error("Delai depasse (~8 min). Recharge la page.");
  }, [refresh, cfg]);

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
        body: JSON.stringify({ secret: secret.trim(), sport: cfg.apiSport }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(data.error || `Impossible d'arreter la comparaison ${cfg.label}.`);
      } else {
        setInfo(data.message || `Comparaison ${cfg.label} arretee.`);
        setStatus({
          status: "cancelled",
          message: "Comparaison annulee par l'utilisateur.",
        });
      }
      await refresh({ silent: true });
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
    setWarning("");
    setInfo("");
    if (!secret.trim()) {
      setError("Saisis ton code secret.");
      return;
    }

    window.localStorage.setItem(SECRET_STORAGE_KEY, secret.trim());
    cfg.clearCache();
    suppressCacheRef.current = true;
    runStartedAtRef.current = new Date().toISOString();
    setBusy(true);
    setPayload(emptyBasketballPayload(cfg.source));
    setCacheSavedAt(null);
    setStatus({ status: "running", message: `Comparaison ${cfg.label} en cours...` });
    setInfo(`Lancement ${cfg.label} en cours...`);
    runAbortRef.current = new AbortController();
    const runSignal = runAbortRef.current.signal;

    try {
      const response = await fetch("/api/trigger", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ secret: secret.trim(), match: match.trim(), sport: cfg.apiSport }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Echec du declenchement.");
      }
      if (typeof data.started_at === "string" && data.started_at.trim()) {
        runStartedAtRef.current = data.started_at.trim();
      }

      setInfo(`Scrape ${cfg.label} live en cours...`);
      await waitForCompletion(runSignal);
      if (runSignal.aborted) {
        return;
      }
      await refresh({ silent: true });
      setInfo(`Comparaison ${cfg.label} terminee.`);
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

  const filterOptions = useMemo(
    () => ({
      statId: statFilter,
      book: bookFilter,
      query: globalSearch,
      matchQuery: displayMatchFilter,
    }),
    [statFilter, bookFilter, globalSearch, displayMatchFilter],
  );

  const comparables = useMemo(
    () => cfg.filterRows(payload?.comparables ?? [], filterOptions),
    [payload, filterOptions, cfg],
  );
  const frHigherRows = useMemo(
    () => cfg.filterRows(payload?.fr_higher_comparables ?? [], filterOptions),
    [payload, filterOptions, cfg],
  );
  const frOnlyRows = useMemo(
    () => cfg.filterRows(payload?.fr_only_comparables ?? [], filterOptions),
    [payload, filterOptions, cfg],
  );
  const fdOnlyRows = useMemo(
    () => cfg.filterRows(payload?.fd_only_comparables ?? [], filterOptions),
    [payload, filterOptions],
  );
  const statCounts = useMemo(
    () => countRowsByStat(payload?.comparables ?? []),
    [payload],
  );
  const matchProgress = useMemo(() => payload?.match_progress ?? [], [payload]);
  const filteredProgress = useMemo(() => {
    const needle = progressSearch.trim().toLowerCase();
    if (!needle) {
      return matchProgress;
    }
    return matchProgress.filter((row) => row.match.toLowerCase().includes(needle));
  }, [matchProgress, progressSearch]);

  const overlapHint = useMemo(() => {
    const notes = payload?.notes ?? [];
    const bookNote = notes.find((note) => /winamax|unibet|betclic|fanduel/i.test(note));
    if (bookNote) {
      return bookNote;
    }
    if ((payload?.comparable_count ?? 0) > 0) {
      return "";
    }
    const fdEvents = payload?.fd_event_count ?? 0;
    const frEvents = payload?.fr_event_count ?? 0;
    if (fdEvents === 0 && (payload?.fr_only_count ?? 0) > 0) {
      return "Des props joueuses existent cote FR, mais FanDuel ne les propose pas sur ces matchs.";
    }
    if (fdEvents > 0 && frEvents === 0) {
      return `FanDuel propose des props ${cfg.label}, mais les books FR n'ont pas de lignes comparables.`;
    }
    if (fdEvents > 0 && frEvents > 0) {
      return "FR et FanDuel ont des props, mais pas sur les memes matchs ou pas aux memes seuils.";
    }
    return "";
  }, [payload]);

  const setSectionOpen = (id: SectionId, open: boolean) => {
    setOpenSections((current) => ({ ...current, [id]: open }));
  };

  const collapseAllSections = () => {
    setOpenSections({
      progress: false,
      comparables: false,
      frHigher: false,
      frOnly: false,
      fdOnly: false,
    });
  };

  const expandAllSections = () => {
    setOpenSections({
      progress: true,
      comparables: true,
      frHigher: true,
      frOnly: true,
      fdOnly: true,
    });
  };

  const allCollapsed = SECTION_IDS.every((id) => !openSections[id]);

  return (
    <>
      <header className="hero">
        <p className="eyebrow">Basket {cfg.label}</p>
        <h1>Props joueurs — books FR vs FanDuel</h1>
        <p className="lead">
          Compare les stats joueurs <strong>points, rebonds, assists, 3pts, combos, paliers</strong>{" "}
          ({cfg.label} — Unibet, Betclic, Winamax) avec FanDuel.
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
          Filtre match au lancement (optionnel)
          <input
            type="text"
            value={match}
            onChange={(event) => setMatch(event.target.value)}
            placeholder="dream, lynx, gray..."
          />
        </label>
        <button type="button" onClick={onSubmit} disabled={busy}>
          {busy ? `Comparaison ${cfg.label}...` : `Lancer comparaison ${cfg.label}`}
        </button>
        {info ? <p className="info">{info}</p> : null}
        {warning ? <p className="warning">{warning}</p> : null}
        {error ? <p className="error">{error}</p> : null}
      </section>

      <RunningBanner
        active={isRunning}
        label={`Comparaison ${cfg.label} en cours`}
        message={status?.message || info || "Scrape live en cours — les anciens resultats ont ete effaces."}
        onCancel={onCancel}
        cancelBusy={cancelBusy}
      />

      <section className="panel filters-panel">
        <div className="filters-header">
          <h2>Filtres affichage</h2>
          <div className="filters-actions">
            <button type="button" className="ghost-btn" onClick={() => refresh().catch(() => undefined)}>
              Rafraichir
            </button>
            <button
              type="button"
              className="ghost-btn"
              onClick={allCollapsed ? expandAllSections : collapseAllSections}
            >
              {allCollapsed ? "Tout deplier" : "Tout replier"}
            </button>
          </div>
        </div>

        <label>
          Recherche globale
          <input
            type="search"
            value={globalSearch}
            onChange={(event) => setGlobalSearch(event.target.value)}
            placeholder="Joueur, match, book, ligne..."
          />
        </label>

        <label>
          Filtrer par match affiche
          <input
            type="search"
            value={displayMatchFilter}
            onChange={(event) => setDisplayMatchFilter(event.target.value)}
            placeholder="dream, sparks, gray..."
          />
        </label>

        <label>
          Book FR
          <select value={bookFilter} onChange={(event) => setBookFilter(event.target.value as WnbaBookFilter)}>
            {cfg.bookFilters.map((book) => (
              <option key={book} value={book}>
                {book}
              </option>
            ))}
          </select>
        </label>

        <div className="filter-chips" role="group" aria-label="Filtrer par stat">
          {cfg.statFilters.map((stat) => {
            const count =
              stat.id === "all"
                ? (payload?.comparable_count ?? 0)
                : (statCounts[stat.id] ?? 0);
            if (stat.id !== "all" && count === 0) {
              return null;
            }
            return (
              <button
                key={stat.id}
                type="button"
                className={`filter-chip${statFilter === stat.id ? " active" : ""}`}
                onClick={() => setStatFilter(stat.id)}
              >
                {stat.label}
                <span className="chip-count">{count}</span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="panel meta">
        <div>
          <span className="meta-label">Derniere mise a jour</span>
          <strong>{formatTimestamp(payload?.generated_at)}</strong>
        </div>
        {cacheSavedAt ? (
          <div>
            <span className="meta-label">Memoire locale</span>
            <strong>{formatTimestamp(cacheSavedAt)}</strong>
          </div>
        ) : null}
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
          <span className="meta-label">Lignes filtrees</span>
          <strong>{comparables.length}</strong>
        </div>
        <div>
          <span className="meta-label">FR paie mieux</span>
          <strong>{frHigherRows.length}</strong>
        </div>
        <div>
          <span className="meta-label">FR sans FD</span>
          <strong>{frOnlyRows.length}</strong>
        </div>
        <div>
          <span className="meta-label">FD sans FR</span>
          <strong>{fdOnlyRows.length}</strong>
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

      <CollapsibleSection
        title="Toutes les props comparees"
        badge={comparables.length}
        open={openSections.comparables}
        onOpenChange={(open) => setSectionOpen("comparables", open)}
      >
        <ResultsTable
          title=""
          rows={comparables}
          marketKind={cfg.marketKind}
          embedded
          showCaptureDetails
          runGeneratedAt={payload?.generated_at}
          emptyMessage="Aucun resultat pour ces filtres. Lance une comparaison ou elargis les filtres."
        />
      </CollapsibleSection>

      <CollapsibleSection
        title="Lignes ou le book FR paie mieux que FanDuel"
        badge={frHigherRows.length}
        open={openSections.frHigher}
        onOpenChange={(open) => setSectionOpen("frHigher", open)}
      >
        <ResultsTable
          title=""
          rows={frHigherRows}
          marketKind={cfg.marketKind}
          embedded
          showCaptureDetails
          runGeneratedAt={payload?.generated_at}
          emptyMessage="Aucune ligne ou la cote FR bat FanDuel pour ces filtres."
        />
      </CollapsibleSection>

      <CollapsibleSection
        title="Props FR sans equivalent FanDuel (meme seuil)"
        badge={frOnlyRows.length}
        open={openSections.frOnly}
        onOpenChange={(open) => setSectionOpen("frOnly", open)}
      >
        <ResultsTable
          title=""
          rows={frOnlyRows}
          marketKind={cfg.marketKind}
          embedded
          showCaptureDetails
          runGeneratedAt={payload?.generated_at}
          emptyMessage="Toutes les lignes FR ont un equivalent FanDuel, ou pas de prop FR."
        />
      </CollapsibleSection>

      <CollapsibleSection
        title="Props FanDuel sans equivalent FR (meme seuil)"
        badge={fdOnlyRows.length}
        open={openSections.fdOnly}
        onOpenChange={(open) => setSectionOpen("fdOnly", open)}
      >
        <ResultsTable
          title=""
          rows={fdOnlyRows}
          marketKind={cfg.marketKind}
          embedded
          showCaptureDetails
          runGeneratedAt={payload?.generated_at}
          emptyMessage="Toutes les lignes FanDuel ont un equivalent FR, ou pas de prop FanDuel."
        />
      </CollapsibleSection>
    </>
  );
}

export function WnbaDashboard() {
  return <BasketballDashboard league="wnba" />;
}
