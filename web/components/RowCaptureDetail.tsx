import type { ComparableRow } from "@/lib/types";

export function formatCaptureTime(value?: string): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("fr-FR", {
    dateStyle: "short",
    timeStyle: "medium",
  });
}

function displayOdds(value?: string): string {
  const trimmed = value?.trim();
  return trimmed ? trimmed : "—";
}

export function RowCaptureDetail({
  row,
  runGeneratedAt,
}: {
  row: ComparableRow;
  runGeneratedAt?: string;
}) {
  const hasPreciseCapture = Boolean(row.fr_captured_at || row.fd_captured_at || row.captured_at);

  return (
    <div className="row-capture-detail">
      <p className="row-capture-title">Detail des cotes (clique pour fermer)</p>
      <dl className="row-capture-list">
        <dt>Cote FR</dt>
        <dd>{displayOdds(row.cote_fr)}</dd>

        <dt>Cote US moneyline</dt>
        <dd>{displayOdds(row.cote_us_fanduel_ml)}</dd>

        <dt>Cote US decimale</dt>
        <dd>{displayOdds(row.cote_fr_fanduel)}</dd>

        <dt>Cote US contraire moneyline</dt>
        <dd>{displayOdds(row.cote_us_fanduel_contraire)}</dd>

        <dt>Cote US contraire decimale</dt>
        <dd>{displayOdds(row.cote_fr_fanduel_contraire)}</dd>
      </dl>

      <p className="row-capture-subtitle">Horodatage du scrape</p>
      <dl className="row-capture-list">
        <dt>Cote FR ({row.bookmaker_fr || "book FR"})</dt>
        <dd>{formatCaptureTime(row.fr_captured_at || row.captured_at || runGeneratedAt)}</dd>

        <dt>Cote FanDuel</dt>
        <dd>{formatCaptureTime(row.fd_captured_at || row.captured_at || runGeneratedAt)}</dd>

        <dt>Run global</dt>
        <dd>{formatCaptureTime(runGeneratedAt || row.captured_at)}</dd>
      </dl>

      {!hasPreciseCapture ? (
        <p className="row-capture-hint">
          Heure precise indisponible pour cette ligne — relance une comparaison pour l&apos;obtenir.
        </p>
      ) : null}
    </div>
  );
}
