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

export function RowCaptureDetail({
  row,
  runGeneratedAt,
}: {
  row: ComparableRow;
  runGeneratedAt?: string;
}) {
  const hasFr = Boolean(row.cote_fr || row.bookmaker_fr);
  const hasFd = Boolean(row.cote_fr_fanduel || row.cote_us_fanduel_ml || row.marche_fanduel);

  return (
    <div className="row-capture-detail">
      <p className="row-capture-title">Horodatage du scrape (clique pour fermer)</p>
      <dl className="row-capture-list">
        {hasFr ? (
          <>
            <dt>Cote FR ({row.bookmaker_fr || "book FR"})</dt>
            <dd>{formatCaptureTime(row.fr_captured_at || row.captured_at || runGeneratedAt)}</dd>
          </>
        ) : null}
        {hasFd ? (
          <>
            <dt>Cote FanDuel</dt>
            <dd>{formatCaptureTime(row.fd_captured_at || row.captured_at || runGeneratedAt)}</dd>
          </>
        ) : null}
        {hasFd && row.cote_us_fanduel_contraire ? (
          <>
            <dt>
              FanDuel contraire{row.issue_fr_contraire ? ` (${row.issue_fr_contraire})` : ""}
            </dt>
            <dd>
              {row.cote_us_fanduel_contraire}
              {row.cote_fr_fanduel_contraire ? ` · ${row.cote_fr_fanduel_contraire} (FR)` : ""}
            </dd>
          </>
        ) : null}
        <dt>Run global</dt>
        <dd>{formatCaptureTime(runGeneratedAt || row.captured_at)}</dd>
      </dl>
      {!row.fr_captured_at && !row.fd_captured_at && !row.captured_at ? (
        <p className="row-capture-hint">
          Heure precise indisponible pour cette ligne — relance une comparaison pour l&apos;obtenir.
        </p>
      ) : null}
    </div>
  );
}
