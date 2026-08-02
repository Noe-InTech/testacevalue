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
  const hasPreciseCapture = Boolean(
    row.fr_captured_at || row.us_captured_at || row.fd_captured_at || row.captured_at,
  );
  const usLabel =
    row.us_source === "rotowire" && row.us_bookmaker
      ? `${row.us_source_label || "RotoWire"} · ${row.us_bookmaker}`
      : row.us_source_label || "FanDuel";
  const usBadgeClass =
    row.us_source === "rotowire" ? "us-source-badge us-source-badge-rotowire" : "us-source-badge us-source-badge-fanduel";

  const bookUrl = row.url_fr?.trim() || "";
  const bookWebFallback = row.url_fr_web?.trim() || "";
  const bookName = row.bookmaker_fr?.trim() || "book FR";
  const isSelectionLink = row.url_fr_kind === "selection";
  const isWinamaxBridge = bookUrl.startsWith("/go/winamax?");
  const bookLinkLabel = isSelectionLink
    ? `Ouvrir le pari sur ${bookName}`
    : `Ouvrir le match sur ${bookName}`;
  // Bridge Winamax stays same-tab so wam:// can hand off to the app before HTTPS fallback.
  const linkTarget = isWinamaxBridge ? undefined : "_blank";
  const linkRel = isWinamaxBridge ? undefined : "noopener noreferrer";

  return (
    <div className="row-capture-detail">
      <p className="row-capture-title">Detail des cotes (clique pour fermer)</p>

      <div className="row-book-link-block">
        <p className="row-capture-subtitle">Lien {bookName}</p>
        {bookUrl ? (
          <a className="row-book-link" href={bookUrl} target={linkTarget} rel={linkRel}>
            {bookLinkLabel}
          </a>
        ) : (
          <p className="row-capture-hint">
            Lien indisponible pour cette ligne — relance une comparaison apres update du runner.
          </p>
        )}
        {bookUrl && !isSelectionLink ? (
          <p className="row-capture-hint">
            Pari precis indisponible pour ce book — ouverture de la page match.
          </p>
        ) : null}
        {isSelectionLink && isWinamaxBridge ? (
          <p className="row-capture-hint">
            Sur mobile avec l&apos;app Winamax : le pari est ajouté au panier. Sur navigateur desktop,
            ouverture de la page match (highlight).
            {bookWebFallback ? (
              <>
                {" "}
                <a href={bookWebFallback} target="_blank" rel="noopener noreferrer">
                  Ouvrir la page match
                </a>
              </>
            ) : null}
          </p>
        ) : null}
      </div>

      <dl className="row-capture-list">
        <dt>Source US</dt>
        <dd>
          <span className={usBadgeClass}>{usLabel}</span>
        </dd>

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

        <dt>Cote US ({usLabel})</dt>
        <dd>{formatCaptureTime(row.us_captured_at || row.fd_captured_at || row.captured_at || runGeneratedAt)}</dd>

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
