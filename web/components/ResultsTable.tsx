import type { ComparableRow, TableColumn } from "@/lib/types";
import { getTableColumns } from "@/lib/types";

interface ResultsTableProps {
  title: string;
  rows: ComparableRow[];
  emptyMessage: string;
  marketKind?: "aces" | "breaks";
  searchQuery?: string;
  embedded?: boolean;
}

function filterRows(rows: ComparableRow[], query: string, marketKind: "aces" | "breaks") {
  const needle = query.trim().toLowerCase();
  if (!needle) {
    return rows;
  }
  const lineKey = marketKind === "breaks" ? "ligne_breaks_fr" : "ligne_aces_fr";
  return rows.filter((row) => {
    const haystack = [
      row.match,
      row.bookmaker_fr,
      row.marche_fr,
      row.marche_fanduel,
      row.ligne_aces_fr,
      row.ligne_breaks_fr,
      row[lineKey as keyof ComparableRow],
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(needle);
  });
}

export function ResultsTable({
  title,
  rows,
  emptyMessage,
  marketKind = "aces",
  searchQuery = "",
  embedded = false,
}: ResultsTableProps) {
  const columns = getTableColumns(marketKind);
  const filtered = filterRows(rows, searchQuery, marketKind);

  const content =
    filtered.length === 0 ? (
      <p className="empty">{emptyMessage}</p>
    ) : (
      <div className="table-wrap">
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
            {filtered.map((row, index) => (
              <tr key={`${row.match}-${row.issue_fr}-${row.marche_fr}-${index}`}>
                {columns.map((column) => (
                  <td
                    key={column.key}
                    data-label={column.label}
                    className={column.key === "meilleur_cote" ? "side" : undefined}
                  >
                    {column.format ? column.format(row) : row[column.key as keyof ComparableRow]}
                  </td>
                ))}
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
