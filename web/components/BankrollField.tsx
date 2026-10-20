"use client";

interface BankrollFieldProps {
  value: string;
  onChange: (value: string) => void;
  invalid?: boolean;
  className?: string;
}

export function BankrollField({ value, onChange, invalid, className }: BankrollFieldProps) {
  return (
    <label className={className ? `bankroll-field ${className}` : "bankroll-field"}>
      Bankroll (€)
      <input
        type="text"
        inputMode="decimal"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="ex. 1000"
        autoComplete="off"
        aria-invalid={invalid || undefined}
      />
      {invalid ? (
        <span className="hint meta-warn">Montant invalide — saisis un nombre &gt; 0.</span>
      ) : (
        <span className="hint">Mises Kelly affichées en € quand la bankroll est renseignée.</span>
      )}
    </label>
  );
}
