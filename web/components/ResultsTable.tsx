import type { ComparableRow } from "@/lib/types";
import { TABLE_COLUMNS } from "@/lib/types";

interface ResultsTableProps {
  title: string;
  rows: ComparableRow[];
  emptyMessage: string;
}

export function ResultsTable({ title, rows, emptyMessage }: ResultsTableProps) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>{title}</h2>
        <span className="badge">{rows.length}</span>
      </div>
      {rows.length === 0 ? (
        <p className="empty">{emptyMessage}</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {TABLE_COLUMNS.map((column) => (
                  <th key={column.key} title={column.hint}>
                    {column.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={`${row.match}-${row.issue_fr}-${row.marche_fr}-${index}`}>
                  {TABLE_COLUMNS.map((column) => (
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
      )}
    </section>
  );
}
