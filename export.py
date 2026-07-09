"""Exporte toutes les cotes par marché et bookmaker dans un fichier CSV."""

import argparse
import csv
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from api_client import OddsApiClient
from config import Config
from markets import collect_allowed_markets
from value_engine import outcome_label

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("export")

SHARP_BOOK = "pinnacle"
OUTPUT_DIR = Path(__file__).parent / "output"

CSV_COLUMNS = [
    "sport",
    "event_id",
    "home_team",
    "away_team",
    "commence_time",
    "market",
    "outcome",
    "line",
    "description",
    "bookmaker",
    "odds",
]


def fetch_odds_rows(
    client: OddsApiClient,
    sport: str,
    bookmakers: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    try:
        events = client.get_events(sport)
    except RuntimeError as e:
        log.warning("Erreur %s : %s", sport, e)
        return rows

    if not events:
        log.info("%s : aucun match à venir", sport)
        return rows

    log.info("%s : %d match(s)", sport, len(events))

    for event in events:
        label = f"{event['home_team']} vs {event['away_team']}"
        event_id = event["id"]

        try:
            markets_resp = client.get_event_markets(sport, event_id, [SHARP_BOOK])
            allowed = collect_allowed_markets(markets_resp, SHARP_BOOK)
        except RuntimeError as e:
            log.warning("  %s : marchés indisponibles (%s)", label, e)
            continue

        if not allowed:
            log.info("  %s : aucun marché autorisé", label)
            continue

        try:
            event_odds = client.get_event_odds(sport, event_id, bookmakers, allowed)
        except RuntimeError as e:
            log.warning("  %s : cotes indisponibles (%s)", label, e)
            continue

        match_rows = 0
        for bm in event_odds.get("bookmakers", []):
            for market in bm.get("markets", []):
                for outcome in market.get("outcomes", []):
                    rows.append(
                        {
                            "sport": sport,
                            "event_id": event_id,
                            "home_team": event["home_team"],
                            "away_team": event["away_team"],
                            "commence_time": event.get("commence_time", ""),
                            "market": market["key"],
                            "outcome": outcome_label(outcome),
                            "line": outcome.get("point", ""),
                            "description": outcome.get("description", ""),
                            "bookmaker": bm["key"],
                            "odds": float(outcome["price"]),
                        }
                    )
                    match_rows += 1

        log.info("  %s : %d ligne(s) exportée(s)", label, match_rows)

    return rows


def write_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def default_output_path() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return OUTPUT_DIR / f"odds_{stamp}.csv"


def run(sports: list[str] | None, output: Path | None) -> Path:
    config = Config.from_env()
    client = OddsApiClient(config.api_key)
    target_sports = sports or config.sports
    output_path = output or default_output_path()

    log.info("Export des cotes")
    log.info("Sports : %s", ", ".join(target_sports))
    log.info("Bookmakers : %s", ", ".join(config.bookmakers))
    log.info("Fichier : %s", output_path)

    all_rows: list[dict[str, Any]] = []
    for sport in target_sports:
        all_rows.extend(fetch_odds_rows(client, sport, config.bookmakers))

    write_csv(all_rows, output_path)

    quota = client.last_quota
    if quota.remaining is not None:
        log.info(
            "Crédits : %d restants | %d utilisés | dernier appel : %d",
            quota.remaining,
            quota.used or 0,
            quota.last_cost or 0,
        )

    log.info("Terminé : %d ligne(s) → %s", len(all_rows), output_path.resolve())
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Exporte les cotes par marché et bookmaker dans un CSV"
    )
    parser.add_argument(
        "--sport",
        action="append",
        dest="sports",
        help="Sport à exporter (répétable). Par défaut : tous les sports du .env",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Chemin du fichier CSV de sortie",
    )
    args = parser.parse_args()
    run(args.sports, args.output)


if __name__ == "__main__":
    main()
