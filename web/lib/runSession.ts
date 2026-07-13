export function isPayloadFromRun(
  payload: { generated_at?: string } | null | undefined,
  runStartedAt: string | null | undefined,
): boolean {
  if (!runStartedAt?.trim()) {
    return true;
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

export function resolveRunStartedAt(
  refValue: string | null | undefined,
  status: { run_started_at?: string } | null | undefined,
): string | null {
  return refValue?.trim() || status?.run_started_at?.trim() || null;
}
