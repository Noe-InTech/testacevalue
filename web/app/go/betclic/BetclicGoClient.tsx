"use client";

import { useEffect, useState } from "react";

type Props = {
  shareUrl: string;
  matchUrl: string;
  selectionId: string;
  matchId: string;
  marketId: string;
};

export function BetclicGoClient({
  shareUrl,
  matchUrl,
  selectionId,
  matchId,
  marketId,
}: Props) {
  const [status, setStatus] = useState(
    shareUrl ? "Ouverture du pari Betclic…" : "Résolution du lien Betclic…",
  );
  const [fallback, setFallback] = useState(matchUrl || "https://www.betclic.fr/");

  useEffect(() => {
    const key = `bc-go:${selectionId}:${matchId}:${marketId}:${shareUrl}`;
    let cancelled = false;

    async function open() {
      try {
        if (sessionStorage.getItem(key)) {
          location.replace(shareUrl || matchUrl || "https://www.betclic.fr/");
          return;
        }
        sessionStorage.setItem(key, "1");
      } catch {
        // ignore storage failures
      }

      let target = shareUrl;
      if (!target && selectionId && matchId && marketId) {
        try {
          const response = await fetch("/api/betclic-share", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              selection_id: selectionId,
              match_id: matchId,
              market_id: marketId,
            }),
          });
          const data = (await response.json().catch(() => ({}))) as {
            url?: string;
            error?: string;
          };
          if (response.ok && data.url) {
            target = data.url;
          } else if (!cancelled) {
            setStatus(
              data.error ||
                "Impossible de préremplir le pari Betclic — ouverture de la page match.",
            );
          }
        } catch {
          if (!cancelled) {
            setStatus("Impossible de préremplir le pari Betclic — ouverture de la page match.");
          }
        }
      }

      const finalUrl = target || matchUrl || "https://www.betclic.fr/";
      if (!cancelled) {
        setFallback(finalUrl);
      }
      location.replace(finalUrl);
    }

    void open();
    return () => {
      cancelled = true;
    };
  }, [shareUrl, matchUrl, selectionId, matchId, marketId]);

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", maxWidth: 520 }}>
      <h1 style={{ fontSize: "1.25rem", marginBottom: "0.75rem" }}>Betclic</h1>
      <p style={{ marginBottom: "1rem" }}>{status}</p>
      <p>
        <a href={fallback}>Continuer sur Betclic</a>
      </p>
    </main>
  );
}
