"""Exporte les ecarts de cotes tennis Unibet vs Betclic vs Winamax."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

OUTPUT_DIR = Path(__file__).parent / "output"


def load_compare_payload(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _max_odds_gap(outcome: dict[str, Any]) -> float:
    unibet_odds = float(outcome.get("unibet_odds", 0.0))
    gaps = []
    for book in ("betclic", "winamax"):
        book_odds = outcome.get(f"{book}_odds")
        if book_odds is not None:
            gaps.append(abs(unibet_odds - float(book_odds)))
    return max(gaps) if gaps else 0.0


def _format_odds(value: float | None) -> str:
    return f"{float(value):.3f}" if value is not None else "-"


def collect_rows(
    payload: dict[str, Any],
    *,
    min_delta: float = 0.0,
    advanced_only: bool = False,
) -> list[dict[str, Any]]:
    rows = []
    for result in payload.get("results", []):
        for market in result.get("comparable_markets", []):
            if advanced_only and not market.get("is_advanced"):
                continue
            for outcome in market.get("outcomes_compared", []):
                delta = _max_odds_gap(outcome)
                if delta < min_delta:
                    continue
                rows.append(
                    {
                        "event": result.get("event_display_fr") or result.get("event", ""),
                        "compare_key": market.get("compare_key", ""),
                        "market_family": market.get("market_family", ""),
                        "is_advanced": market.get("is_advanced", False),
                        "unibet_market_label": market.get("unibet_market_label", ""),
                        "betclic_market_label": market.get("betclic_market_label", ""),
                        "winamax_market_label": market.get("winamax_market_label", ""),
                        "outcome": outcome.get("outcome", ""),
                        "unibet_odds": float(outcome.get("unibet_odds", 0.0)),
                        "betclic_odds": outcome.get("betclic_odds"),
                        "winamax_odds": outcome.get("winamax_odds"),
                        "best_bookmaker": outcome.get("best_bookmaker", ""),
                    }
                )
    rows.sort(
        key=lambda row: max(
            abs(float(row.get("unibet_odds", 0.0)) - float(row.get("betclic_odds") or 0.0)),
            abs(float(row.get("unibet_odds", 0.0)) - float(row.get("winamax_odds") or 0.0)),
        ),
        reverse=True,
    )
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
    lines = [
        "# Comparatif cotes tennis Unibet vs Betclic vs Winamax",
        "",
        f"Source: `{source_name}`",
        "",
        "Note: Betclic n'expose en SSR que les marches principaux. Winamax fournit les marches "
        "avances (breaks/tie-breaks) via Socket.IO.",
        "",
        f"Nombre d'issues retenues: **{len(rows)}**",
        "",
    ]
    current_event = None
    for idx, row in enumerate(rows):
        if row["event"] != current_event:
            current_event = row["event"]
            if idx:
                lines.append("")
            lines.append(f"## {current_event}")
            lines.append("")
            lines.append("| Marche | Issue | Unibet | Betclic | Winamax | Meilleur |")
            lines.append("| --- | --- | ---: | ---: | ---: | --- |")
        market_name = row["unibet_market_label"] or row["compare_key"]
        lines.append(
            f"| {market_name} | {row['outcome']} | {row['unibet_odds']:.3f} | "
            f"{_format_odds(row.get('betclic_odds'))} | {_format_odds(row.get('winamax_odds'))} | "
            f"{row['best_bookmaker']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Exporte les ecarts tennis Unibet vs Betclic vs Winamax")
    parser.add_argument("input", type=Path, help="Fichier JSON compare_tennis_books")
    parser.add_argument("--csv-output", type=Path)
    parser.add_argument("--md-output", type=Path)
    parser.add_argument("--min-delta", type=float, default=0.0)
    parser.add_argument("--advanced-only", action="store_true")
    args = parser.parse_args()

    payload = load_compare_payload(args.input)
    rows = collect_rows(payload, min_delta=args.min_delta, advanced_only=args.advanced_only)

    stem = args.input.stem.replace("tennis_books_compare_", "tennis_books_diff_")
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
