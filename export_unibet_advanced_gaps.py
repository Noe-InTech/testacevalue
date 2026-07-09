"""Exporte les marchés avancés Unibet non couverts par Betclic."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

OUTPUT_DIR = Path(__file__).parent / "output"


def load_compare_payload(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def collect_gap_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in payload.get("results", []):
        for item in result.get("unibet_only_markets", []):
            if not item.get("is_advanced"):
                continue
            rows.append(
                {
                    "event": result.get("event_display_fr") or result.get("event", ""),
                    "competition": result.get("competition", ""),
                    "compare_key": item.get("compare_key", ""),
                    "market_family": item.get("market_family", ""),
                    "market_label_raw": item.get("market_label_raw", ""),
                    "betclic_open_market_count": result.get("betclic_open_market_count", 0),
                    "betclic_ssr_market_count": result.get("betclic_ssr_market_count", 0),
                }
            )
    rows.sort(key=lambda row: (row["event"], row["market_family"], row["compare_key"]))
    return rows


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if rows:
            writer.writeheader()
            writer.writerows(rows)


def write_markdown(rows: list[dict[str, Any]], path: Path, source_name: str) -> None:
    family_counts = Counter(row["market_family"] for row in rows)
    lines = [
        "# Marches avances Unibet non couverts par Betclic",
        "",
        f"Source: `{source_name}`",
        "",
        f"Nombre total de gaps avances: **{len(rows)}**",
        "",
        "## Repartition par famille",
        "",
        "| Famille | Count |",
        "| --- | ---: |",
    ]
    for family, count in sorted(family_counts.items()):
        lines.append(f"| {family} | {count} |")

    current_event = None
    for row in rows:
        if row["event"] != current_event:
            current_event = row["event"]
            lines.extend(
                [
                    "",
                    f"## {current_event}",
                    "",
                    "| Famille | Cle compare | Libelle Unibet | Betclic SSR / total |",
                    "| --- | --- | --- | ---: |",
                ]
            )
        lines.append(
            f"| {row['market_family']} | `{row['compare_key']}` | {row['market_label_raw']} | "
            f"{row['betclic_ssr_market_count']} / {row['betclic_open_market_count']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Exporte les gaps avances Unibet vs Betclic")
    parser.add_argument("input", type=Path, help="Fichier JSON compare_tennis_books")
    parser.add_argument("--csv-output", type=Path)
    parser.add_argument("--md-output", type=Path)
    args = parser.parse_args()

    payload = load_compare_payload(args.input)
    rows = collect_gap_rows(payload)

    stem = args.input.stem.replace("tennis_books_compare_", "unibet_advanced_gaps_")
    csv_path = args.csv_output or OUTPUT_DIR / f"{stem}.csv"
    md_path = args.md_output or OUTPUT_DIR / f"{stem}.md"
    write_csv(rows, csv_path)
    write_markdown(rows, md_path, args.input.name)
    print(f"CSV: {csv_path}")
    print(f"MD: {md_path}")
    print(f"Rows: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
