"use client";

import type { ValueBetRow } from "@/lib/mptoValue";

interface ValuesTableProps {
  title: string;
  rows: ValueBetRow[];
  emptyMessage: string;
  embedded?: boolean;
  searchQuery?: string;
}

function filterRows(rows: ValueBetRow[], query: string): ValueBetRow[] {
  const needle = query.trim().toLowerCase();
  if (!needle) {
    return rows;
  }
  return rows.filter((row) =>
    [row.match, row.bet, row.opposite, row.bookmaker, row.coteFd, row.coteFr]
      .join(" ")
      .toLowerCase()
      .includes(needle),
  );
}

function rowKey(row: ValueBetRow, index: number): string {
  return [row.match, row.compareKey, row.bet, row.bookmaker, index].filter(Boolean).join("|");
}

export function ValuesTable({
  title,
  rows,
  emptyMessage,
  embedded = false,
  searchQuery = "",
}: ValuesTableProps) {
  const filtered = filterRows(rows, searchQuery);

  const content =
    filtered.length === 0 ? (
      <p className="empty">{emptyMessage}</p>
    ) : (
      <div className="table-wrap">
        <p className="table-hint">
          Edge MPTO (ref. FanDuel) · Kelly fractionne a 0,25 · uniquement si la cote FR bat FanDuel.
        </p>
        <table className="values-table">
          <thead>
            <tr>
              <th>Match</th>
              <th>Pari</th>
              <th>Contraire</th>
              <th>Cote FD</th>
              <th>Cote FR</th>
              <th>Book</th>
              <th>Edge</th>
              <th>Mise Kelly 0,25</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row, index) => (
              <tr key={rowKey(row, index)}>
                <td data-label="Match">{row.match}</td>
                <td data-label="Pari">{row.bet}</td>
                <td data-label="Contraire">{row.opposite}</td>
                <td data-label="Cote FD">{row.coteFd}</td>
                <td data-label="Cote FR">{row.coteFr}</td>
                <td data-label="Book">{row.bookmaker}</td>
                <td data-label="Edge" className="value-edge">
                  {row.edgeLabel}
                </td>
                <td data-label="Mise Kelly 0,25" className="value-kelly">
                  {row.kellyLabel}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );

  if (embedded) {
    return content;
  }

  return (
    <section className="panel values-panel">
      <div className="panel-header">
        <h2>{title}</h2>
        <span className="badge badge-success">{filtered.length}</span>
      </div>
      {content}
    </section>
  );
}
