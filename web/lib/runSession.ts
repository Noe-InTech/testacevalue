export function isPayloadFromRun(
  payload: { generated_at?: string } | null | undefined,
  runStartedAt: string | null | undefined,
): boolean {
  if (!runStartedAt?.trim()) {
    return false;
  }
  const generatedAt = payload?.generated_at?.trim();
  if (!generatedAt) {
    return false;
  }
  const payloadMs = Date.parse(generatedAt);
  const runMs = Date.parse(runStartedAt);
  if (Number.isNaN(payloadMs) || Number.isNaN(runMs)) {
    return false;
  }
  return payloadMs >= runMs - 2000;
}

/** Ne pas réafficher le localStorage pendant un scrape actif ou juste après reset. */
export function shouldUseLocalResultsCache(options: {
  runnerStatus?: string | null;
  suppressCache: boolean;
}): boolean {
  if (options.suppressCache) {
    return false;
  }
  if (options.runnerStatus === "running") {
    return false;
  }
  return true;
}

/** Accepte le JSON runner seulement s'il correspond au run en cours ou au dernier run terminé. */
export function shouldApplyRunnerPayload(
  payload: { generated_at?: string } | null | undefined,
  status: { status?: string; run_started_at?: string; generated_at?: string } | null | undefined,
  runStartedAt: string | null | undefined,
  hasData: boolean,
): boolean {
  if (!payload || !hasData) {
    return false;
  }
  const runStart = resolveRunStartedAt(runStartedAt, status);
  if (status?.status === "running" || runStartedAt?.trim()) {
    return isPayloadFromRun(payload, runStart);
  }
  const generatedAt = payload.generated_at?.trim();
  if (!generatedAt) {
    return false;
  }
  const statusGeneratedAt = status?.generated_at?.trim();
  if (status?.status === "success" && statusGeneratedAt) {
    const payloadMs = Date.parse(generatedAt);
    const statusMs = Date.parse(statusGeneratedAt);
    if (!Number.isNaN(payloadMs) && !Number.isNaN(statusMs) && payloadMs + 5000 < statusMs) {
      return false;
    }
  }
  return true;
}

export function resolveRunStartedAt(
  refValue: string | null | undefined,
  status: { run_started_at?: string } | null | undefined,
): string | null {
  return refValue?.trim() || status?.run_started_at?.trim() || null;
}
