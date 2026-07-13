"use client";

interface RunningBannerProps {
  active: boolean;
  label: string;
  message?: string;
  onCancel?: () => void;
  cancelBusy?: boolean;
}

export function RunningBanner({
  active,
  label,
  message,
  onCancel,
  cancelBusy = false,
}: RunningBannerProps) {
  if (!active) {
    return null;
  }

  return (
    <section className="panel running-banner" role="status" aria-live="polite">
      <div className="running-banner-main">
        <span className="running-dot" aria-hidden="true" />
        <div className="running-banner-text">
          <strong>{label}</strong>
          {message ? <span>{message}</span> : null}
        </div>
      </div>
      {onCancel ? (
        <button
          type="button"
          className="running-stop-btn"
          onClick={onCancel}
          disabled={cancelBusy}
        >
          {cancelBusy ? "Arret..." : "Arreter"}
        </button>
      ) : null}
    </section>
  );
}
