import type { ApiPayload, MarketPayload, RunStatus } from "@/lib/types";
import { isCombinedPayload } from "@/lib/types";

export interface DisplayRunMeta {
  statusLabel: string;
  stepLabel: string;
  tone: "ok" | "warn" | "idle" | "running";
}

function hasUsablePayload(payload: ApiPayload | null | undefined): boolean {
  if (!payload) {
    return false;
  }
  if (isCombinedPayload(payload)) {
    return (
      (payload.matches_done ?? 0) > 0 ||
      (payload.aces?.comparable_count ?? 0) > 0 ||
      (payload.breaks?.comparable_count ?? 0) > 0 ||
      (payload.victoires?.comparable_count ?? 0) > 0 ||
      (payload.aces?.comparables?.length ?? 0) > 0
    );
  }
  const market = payload as MarketPayload;
  return (
    (market.comparable_count ?? 0) > 0 ||
    (market.fr_only_count ?? 0) > 0 ||
    (market.fd_only_count ?? 0) > 0 ||
    (market.comparables?.length ?? 0) > 0 ||
    (market.matches_done ?? 0) > 0
  );
}

/** Affichage statut/étape unifié (tennis / WNBA / NBA / baseball). */
export function getDisplayRunMeta(
  status: RunStatus | null | undefined,
  payload: ApiPayload | null | undefined,
): DisplayRunMeta {
  const rawStatus = status?.status ?? "idle";
  const rawMessage = (status?.message || "").trim();
  const usable = hasUsablePayload(payload);
  const interrupted =
    /interrompue|process mort|timeout|runner redemarre|run precedent ignore/i.test(rawMessage);
  const partial = Boolean(payload && "partial" in payload && payload.partial);

  if (rawStatus === "running") {
    return {
      statusLabel: partial ? "running (partiel)" : "running",
      stepLabel: rawMessage || "Comparaison en cours...",
      tone: "running",
    };
  }

  if (rawStatus === "cancelled") {
    return {
      statusLabel: "annule",
      stepLabel: rawMessage || "Comparaison annulee.",
      tone: "warn",
    };
  }

  if (rawStatus === "error" || interrupted) {
    if (usable) {
      return {
        statusLabel: partial ? "pret (partiel)" : "pret",
        stepLabel: rawMessage || "Dernier run interrompu — resultats affiches. Tu peux relancer.",
        tone: "warn",
      };
    }
    return {
      statusLabel: "erreur",
      stepLabel: rawMessage || "La comparaison a echoue.",
      tone: "warn",
    };
  }

  if (rawStatus === "success") {
    return {
      statusLabel: partial ? "termine (partiel)" : "termine",
      stepLabel: rawMessage || "Comparaison terminee.",
      tone: "ok",
    };
  }

  return {
    statusLabel: usable ? (partial ? "pret (partiel)" : "pret") : "idle",
    stepLabel: rawMessage || (usable ? "Resultats disponibles." : "—"),
    tone: usable ? "ok" : "idle",
  };
}
