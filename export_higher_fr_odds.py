"""Exporte les issues ou la meilleure cote FR est superieure a Pinnacle."""

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
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


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

                eligible_prices.sort(key=lambda item: item.get("odds", 0), reverse=True)
                best_price = eligible_prices[0]
                best_fr = best_price.get("odds")
                pinnacle = outcome.get("pinnacle_odds")
                delta = None if best_fr is None or pinnacle is None else best_fr - pinnacle
                if best_fr is None or pinnacle is None or delta is None:
                    continue
                if best_fr <= pinnacle:
                    continue
                rows.append(
                    {
                        "event": result.get("event_display_fr", result.get("event", "")),
                        "pinnacle_key": market.get("pinnacle_key", ""),
                        "coteur_market_label": market.get("coteur_market_label", ""),
                        "coteur_market_special": market.get("coteur_market_special", ""),
                        "line": market.get("line", ""),
                        "outcome": outcome.get("outcome", ""),
                        "pinnacle_odds": pinnacle,
                        "best_fr_odds": best_fr,
                        "best_fr_bookmaker": best_price.get("bookmaker", ""),
                        "price_delta": delta,
                    }
                )
    rows.sort(
        key=lambda row: (
            -float(row["price_delta"]),
            row["event"],
            row["pinnacle_key"],
            row["outcome"],
        )
    )
    return rows


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "event",
                "pinnacle_key",
                "coteur_market_label",
                "coteur_market_special",
                "line",
                "outcome",
                "pinnacle_odds",
                "best_fr_odds",
                "best_fr_bookmaker",
                "price_delta",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict[str, Any]], path: Path, source_name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Comparatif cotes FR vs Pinnacle",
        "",
        f"Source: `{source_name}`",
        "",
        "Filtre: uniquement les issues ou la meilleure cote FR est superieure a Pinnacle.",
        "",
        f"Nombre d'issues retenues: **{len(rows)}**",
        "",
    ]

    if not rows:
        lines.append("Aucune issue avec une cote FR superieure a Pinnacle.")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    current_event = None
    for idx, row in enumerate(rows):
        if row["event"] != current_event:
            current_event = row["event"]
            lines.extend(
                [
                    f"## {current_event}",
                    "",
                    "| Marche | Issue | Cote US (Pinnacle) | Cote FR | Bookmaker FR | Ecart FR - US |",
                    "| --- | --- | ---: | ---: | --- | ---: |",
                ]
            )
        market_bits = [row["coteur_market_label"] or row["pinnacle_key"]]
        if row["coteur_market_special"]:
            market_bits.append(str(row["coteur_market_special"]))
        elif row["line"]:
            market_bits.append(str(row["line"]))
        market_name = " ".join(bit for bit in market_bits if bit)
        lines.append(
            f"| {market_name} | {row['outcome']} | {row['pinnacle_odds']:.3f} | {row['best_fr_odds']:.3f} | {row['best_fr_bookmaker']} | {row['price_delta']:+.3f} |"
        )
        next_index = idx + 1
        if next_index < len(rows) and rows[next_index]["event"] != current_event:
            lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def default_output_paths(input_path: Path) -> tuple[Path, Path]:
    stem = input_path.stem.replace("market_compare_", "higher_fr_than_pinnacle_")
    return (
        OUTPUT_DIR / f"{stem}.csv",
        OUTPUT_DIR / f"{stem}.md",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exporte seulement les issues ou la meilleure cote FR est superieure a Pinnacle."
    )
    parser.add_argument("input", type=Path, help="Fichier JSON compare_markets")
    parser.add_argument("--csv-output", type=Path, help="Fichier CSV de sortie")
    parser.add_argument("--md-output", type=Path, help="Fichier Markdown de sortie")
    parser.add_argument(
        "--bookmakers",
        default=",".join(sorted(DEFAULT_ALLOWED_BOOKMAKERS)),
        help="Liste CSV des bookmakers FR autorises",
    )
    args = parser.parse_args()

    payload = load_compare_payload(args.input)
    allowed = {item.strip().lower() for item in args.bookmakers.split(",") if item.strip()}
    rows = collect_positive_rows(payload, allowed)
    csv_path, md_path = default_output_paths(args.input)
    csv_path = args.csv_output or csv_path
    md_path = args.md_output or md_path

    write_csv(rows, csv_path)
    write_markdown(rows, md_path, args.input.name)

    print(f"CSV: {csv_path}")
    print(f"MD: {md_path}")
    print(f"Rows: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
