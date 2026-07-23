"use client";

import { Fragment, useState } from "react";

import { RowCaptureDetail } from "@/components/RowCaptureDetail";
import type { ComparableRow, MarketKind, TableColumn } from "@/lib/types";
import { getTableColumns } from "@/lib/types";

interface ResultsTableProps {
  title: string;
  rows: ComparableRow[];
  emptyMessage: string;
  marketKind?: MarketKind;
  searchQuery?: string;
  embedded?: boolean;
  runGeneratedAt?: string;
  showCaptureDetails?: boolean;
}

function filterRows(rows: ComparableRow[], query: string, marketKind: MarketKind) {
  const needle = query.trim().toLowerCase();
  if (!needle) {
    return rows;
  }
  const lineKey =
    marketKind === "breaks"
      ? "ligne_breaks_fr"
      : marketKind === "wnba" || marketKind === "nba"
        ? "ligne_props_fr"
        : "ligne_aces_fr";
  return rows.filter((row) => {
    const haystack = [
      row.match,
      row.bookmaker_fr,
      row.marche_fr,
      row.marche_fanduel,
      row.ligne_aces_fr,
      row.ligne_breaks_fr,
      row.ligne_props_fr,
      row[lineKey as keyof ComparableRow],
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(needle);
  });
}

function rowKey(row: ComparableRow, index: number): string {
  return [
    row.match,
    row.compare_key,
    row.issue_fr,
    row.marche_fr,
    row.bookmaker_fr,
    row.ligne_props_fr,
    index,
  ]
    .filter(Boolean)
    .join("|");
}

export function ResultsTable({
  title,
  rows,
  emptyMessage,
  marketKind = "aces",
  searchQuery = "",
  embedded = false,
  runGeneratedAt,
  showCaptureDetails = false,
}: ResultsTableProps) {
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const columns = getTableColumns(marketKind);
  const filtered = filterRows(rows, searchQuery, marketKind);

  const content =
    filtered.length === 0 ? (
      <p className="empty">{emptyMessage}</p>
    ) : (
      <div className="table-wrap">
        {showCaptureDetails ? (
          <p className="table-hint">
            Clique sur une ligne pour voir le detail des cotes (FR, US ML, US decimale, contraire) et
            l&apos;heure de capture.
          </p>
        ) : null}
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column.key} title={column.hint}>
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((row, index) => {
              const key = rowKey(row, index);
              const selected = selectedKey === key;
              return (
                <Fragment key={key}>
                  <tr
                    className={showCaptureDetails ? `clickable-row${selected ? " selected" : ""}` : undefined}
                    onClick={
                      showCaptureDetails
                        ? () => setSelectedKey(selected ? null : key)
                        : undefined
                    }
                  >
                    {columns.map((column) => (
                      <td
                        key={column.key}
                        data-label={column.label}
                        className={column.key === "meilleur_cote" ? "side" : undefined}
                      >
                        {"format" in column && column.format
                          ? column.format(row)
                          : row[column.key as keyof ComparableRow]}
                      </td>
                    ))}
                  </tr>
                  {showCaptureDetails && selected ? (
                    <tr className="row-detail">
                      <td colSpan={columns.length}>
                        <RowCaptureDetail row={row} runGeneratedAt={runGeneratedAt} />
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    );

  if (embedded) {
    return content;
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>{title}</h2>
        <span className="badge">{filtered.length}</span>
      </div>
      {content}
    </section>
  );
}

export type { TableColumn };
