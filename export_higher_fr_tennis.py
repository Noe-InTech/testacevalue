"""Exporte les issues tennis ou la meilleure cote FR est superieure a FanDuel."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

OUTPUT_DIR = Path(__file__).parent / "output"
DEFAULT_ALLOWED_BOOKMAKERS = {
    "betsson",
    "unibet",
    "pmu",
    "winamax",
    "betclic",
    "bet365",
}


def load_compare_payload(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def collect_positive_rows(
    payload: dict[str, Any],
    allowed_bookmakers: set[str] | None = None,
) -> list[dict[str, Any]]:
    rows = []
    allowed = {name.lower() for name in (allowed_bookmakers or set())}
    for result in payload.get("results", []):
        for market in result.get("comparable_markets", []):
            for outcome in market.get("outcomes_compared", []):
                eligible_prices = []
                for price in outcome.get("coteur_prices", []):
                    bookmaker = str(price.get("bookmaker", ""))
                    if allowed and bookmaker.lower() not in allowed:
                        continue
                    eligible_prices.append(price)
                if not eligible_prices:
                    continue
                best = max(eligible_prices, key=lambda item: item["odds"])
                fanduel_odds = outcome.get("fanduel_odds")
                if fanduel_odds is None or best["odds"] <= fanduel_odds:
                    continue
                rows.append(
                    {
                        "event": result.get("event_display_fr") or result.get("event", ""),
                        "fanduel_key": market.get("fanduel_key", ""),
                        "coteur_market_label": market.get("coteur_market_label", ""),
                        "coteur_market_special": market.get("coteur_market_special", ""),
                        "outcome": outcome.get("outcome", ""),
                        "fanduel_odds": float(fanduel_odds),
                        "best_fr_odds": float(best["odds"]),
                        "best_fr_bookmaker": best.get("bookmaker", ""),
                        "price_delta": float(best["odds"]) - float(fanduel_odds),
                    }
                )
    rows.sort(key=lambda row: row["price_delta"], reverse=True)
    return rows


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)


def write_markdown(rows: list[dict[str, Any]], path: Path, source_name: str) -> None:
    lines = [
        "# Comparatif cotes tennis FR vs FanDuel",
        "",
        f"Source: `{source_name}`",
        "",
        "Filtre: uniquement les issues ou la meilleure cote FR whitelist est superieure a FanDuel.",
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
            lines.append("| Marche | Issue | FanDuel | Cote FR | Bookmaker FR | Ecart FR - FD |")
            lines.append("| --- | --- | ---: | ---: | --- | ---: |")
        market_name = row["coteur_market_label"] or row["fanduel_key"]
        lines.append(
            f"| {market_name} | {row['outcome']} | {row['fanduel_odds']:.3f} | "
            f"{row['best_fr_odds']:.3f} | {row['best_fr_bookmaker']} | {row['price_delta']:+.3f} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Exporte les values tennis FR > FanDuel")
    parser.add_argument("input", type=Path, help="Fichier JSON compare_tennis_markets")
    parser.add_argument("--csv-output", type=Path)
    parser.add_argument("--md-output", type=Path)
    parser.add_argument(
        "--bookmakers",
        default=",".join(sorted(DEFAULT_ALLOWED_BOOKMAKERS)),
    )
    args = parser.parse_args()

    payload = load_compare_payload(args.input)
    allowed = {item.strip().lower() for item in args.bookmakers.split(",") if item.strip()}
    rows = collect_positive_rows(payload, allowed)

    stem = args.input.stem.replace("tennis_compare_", "tennis_higher_fr_than_fanduel_")
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
