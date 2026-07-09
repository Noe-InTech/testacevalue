"""Compare les marchés et cotes tennis Coteur vs FanDuel."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from coteur_client import CoteurClient
from fanduel_client import FanDuelClient, page_id_candidates_from_urls, runner_decimal_odds
from scrape_coteur import build_bookmaker_name, normalize_bookmaker_name
from tennis_market_mapping import (
    coteur_handicap_outcome_label,
    coteur_market_label,
    coteur_outcome_label,
    fanduel_runner_label,
    map_coteur_to_fanduel,
    map_fanduel_market_to_compare_key,
    normalize_player,
    players_match as tennis_players_match,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("compare_tennis")

OUTPUT_DIR = Path(__file__).parent / "output"


def players_match(name_a: str, name_b: str) -> bool:
    return tennis_players_match(name_a, name_b)


def match_coteur_to_fanduel_event(
    coteur_data: dict[str, Any],
    fanduel_events: list[dict[str, Any]],
) -> dict[str, Any] | None:
    info = coteur_data.get("info") or {}
    home = (info.get("teamDom") or {}).get("equipeNom", "")
    away = (info.get("teamExt") or {}).get("equipeNom", "")

    for event in fanduel_events:
        fd_home = event.get("home_player", "")
        fd_away = event.get("away_player", "")
        if players_match(home, fd_home) and players_match(away, fd_away):
            return event
        if players_match(home, fd_away) and players_match(away, fd_home):
            return event
    return None


def build_fanduel_variant_map(event: dict[str, Any]) -> dict[str, dict[str, Any]]:
    variant_map: dict[str, dict[str, Any]] = {}
    home = event.get("home_player", "")
    away = event.get("away_player", "")

    for market in event.get("markets", []):
        compare_key = map_fanduel_market_to_compare_key(market)
        if not compare_key:
            continue
        outcomes = []
        for runner in market.get("runners", []):
            if runner.get("runnerStatus") not in (None, "ACTIVE"):
                continue
            odds = runner_decimal_odds(runner)
            if odds is None:
                continue
            raw_name = str(runner.get("runnerName", ""))
            outcomes.append(
                {
                    "label": fanduel_runner_label(compare_key, raw_name, home, away),
                    "raw_name": raw_name,
                    "odds": odds,
                }
            )
        if not outcomes:
            continue
        existing = variant_map.get(compare_key)
        if existing and len(existing["outcomes"]) >= len(outcomes):
            continue
        variant_map[compare_key] = {
            "compare_key": compare_key,
            "market_name": market.get("marketName", ""),
            "outcomes": outcomes,
        }
    return variant_map


def build_coteur_variant_rows(
    coteur: CoteurClient,
    match: dict[str, Any],
    coteur_data: dict[str, Any],
    bookmaker_names: dict[int, str],
) -> list[dict[str, Any]]:
    info = coteur_data.get("info") or {}
    home_player = (info.get("teamDom") or {}).get("equipeNom", "")
    away_player = (info.get("teamExt") or {}).get("equipeNom", "")

    variants = []
    for entry in coteur_data.get("odds", []):
        typename = entry.get("typename", "")
        special = entry.get("special") or ""
        fanduel_key = map_coteur_to_fanduel(typename, special)
        market_data = coteur.get_market_odds(match["renc_id"], typename, special)
        outcome_map: dict[str, list[dict[str, Any]]] = {}
        bookmakers = []
        for value in market_data.get("values", []):
            bookmaker_id = value.get("bookId")
            bookmaker_name = build_bookmaker_name(bookmaker_id, bookmaker_names)
            bookmakers.append(
                {
                    "bookmaker_id": bookmaker_id,
                    "bookmaker": bookmaker_name,
                    "disabled": bool(value.get("disable", False)),
                    "last_update": value.get("lastUpdate", ""),
                }
            )
            for raw_outcome, odds in (value.get("current") or {}).items():
                if typename == "12" and ":" in special:
                    label = coteur_handicap_outcome_label(special, str(raw_outcome), home_player, away_player)
                else:
                    label = coteur_outcome_label(typename, str(raw_outcome), home_player, away_player)
                outcome_map.setdefault(label, []).append(
                    {
                        "raw_outcome": str(raw_outcome),
                        "bookmaker_id": bookmaker_id,
                        "bookmaker": bookmaker_name,
                        "odds": odds,
                        "previous_odds": (value.get("previous") or {}).get(raw_outcome, ""),
                        "disabled": bool(value.get("disable", False)),
                        "last_update": value.get("lastUpdate", ""),
                    }
                )
        variants.append(
            {
                "market_type": typename,
                "market_special": special,
                "market_label": coteur_market_label(typename, special),
                "fanduel_key": fanduel_key,
                "outcomes": outcome_map,
                "bookmakers": bookmakers,
            }
        )
    return variants


def compare_match(
    coteur: CoteurClient,
    coteur_match: dict[str, Any],
    fanduel_event: dict[str, Any],
    bookmaker_names: dict[int, str],
    coteur_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    coteur_data = coteur_data or coteur.get_full_odds(coteur_match["renc_id"])
    info = coteur_data.get("info") or {}
    home_player = (info.get("teamDom") or {}).get("equipeNom", "")
    away_player = (info.get("teamExt") or {}).get("equipeNom", "")

    fanduel_variants = build_fanduel_variant_map(fanduel_event)
    coteur_variants = build_coteur_variant_rows(coteur, coteur_match, coteur_data, bookmaker_names)

    comparable_markets = []
    coteur_only = []
    grouped_variants: dict[str, list[dict[str, Any]]] = {}
    for variant in coteur_variants:
        grouped_variants.setdefault(variant["fanduel_key"] or "", []).append(variant)

    for key, variants in grouped_variants.items():
        if not key or key not in fanduel_variants:
            for variant in variants:
                coteur_only.append(
                    {
                        "market_type": variant["market_type"],
                        "market_special": variant["market_special"],
                        "fanduel_key": variant["fanduel_key"],
                    }
                )
            continue

        fd = fanduel_variants[key]
        best_market = None
        best_score = (-1, -1, -1.0)
        saw_no_common = False

        for variant in variants:
            outcome_labels = sorted(set(variant["outcomes"]).intersection({o["label"] for o in fd["outcomes"]}))
            if not outcome_labels:
                saw_no_common = True
                continue
            outcome_comparisons = []
            total_price_count = 0
            total_best_odds = 0.0
            for label in outcome_labels:
                fd_outcome = next(o for o in fd["outcomes"] if o["label"] == label)
                coteur_prices = sorted(
                    variant["outcomes"][label],
                    key=lambda item: item["odds"],
                    reverse=True,
                )
                total_price_count += len(coteur_prices)
                total_best_odds += float(coteur_prices[0]["odds"]) if coteur_prices else 0.0
                outcome_comparisons.append(
                    {
                        "outcome": label,
                        "fanduel_odds": fd_outcome["odds"],
                        "coteur_prices": coteur_prices,
                        "best_coteur_price": coteur_prices[0]["odds"] if coteur_prices else None,
                        "best_coteur_bookmaker": coteur_prices[0]["bookmaker"] if coteur_prices else None,
                        "price_delta": (coteur_prices[0]["odds"] - fd_outcome["odds"]) if coteur_prices else None,
                    }
                )

            score = (len(outcome_comparisons), total_price_count, total_best_odds)
            if score > best_score:
                best_score = score
                best_market = {
                    "fanduel_key": key,
                    "fanduel_market_name": fd["market_name"],
                    "coteur_market_type": variant["market_type"],
                    "coteur_market_special": variant["market_special"],
                    "coteur_market_label": variant["market_label"],
                    "outcomes_compared": outcome_comparisons,
                    "matched_outcomes_count": len(outcome_comparisons),
                    "coteur_outcomes_count": len(variant["outcomes"]),
                    "fanduel_outcomes_count": len(fd["outcomes"]),
                }

        if best_market is not None:
            comparable_markets.append(best_market)
            continue

        for variant in variants:
            coteur_only.append(
                {
                    "market_type": variant["market_type"],
                    "market_special": variant["market_special"],
                    "fanduel_key": key,
                    "reason": "no_common_outcomes" if saw_no_common else "",
                }
            )

    fanduel_only = sorted(set(fanduel_variants) - {m["fanduel_key"] for m in comparable_markets})

    return {
        "event": fanduel_event.get("event", ""),
        "event_display_fr": f"{home_player} vs {away_player}",
        "commence_time": info.get("rencDate", fanduel_event.get("open_date", "")),
        "coteur_renc_id": coteur_match["renc_id"],
        "coteur_url": coteur_match["url"],
        "fanduel_event_id": fanduel_event.get("event_id", ""),
        "is_doubles": bool(fanduel_event.get("is_doubles")),
        "comparable_market_count": len(comparable_markets),
        "comparable_markets": comparable_markets,
        "coteur_only_markets": coteur_only,
        "fanduel_only_markets": fanduel_only,
        "fanduel_market_count": len(fanduel_event.get("markets", [])),
        "coteur_market_count": len(coteur_variants),
    }


def write_csv_rows(results: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "event",
                "event_display_fr",
                "fanduel_key",
                "coteur_market_type",
                "coteur_market_special",
                "outcome",
                "fanduel_odds",
                "best_coteur_odds",
                "best_coteur_bookmaker",
                "price_delta",
            ],
        )
        writer.writeheader()
        for result in results:
            for market in result["comparable_markets"]:
                for outcome in market["outcomes_compared"]:
                    writer.writerow(
                        {
                            "event": result["event"],
                            "event_display_fr": result["event_display_fr"],
                            "fanduel_key": market["fanduel_key"],
                            "coteur_market_type": market["coteur_market_type"],
                            "coteur_market_special": market["coteur_market_special"],
                            "outcome": outcome["outcome"],
                            "fanduel_odds": outcome["fanduel_odds"],
                            "best_coteur_odds": outcome["best_coteur_price"],
                            "best_coteur_bookmaker": outcome["best_coteur_bookmaker"],
                            "price_delta": outcome["price_delta"],
                        }
                    )


def print_summary(results: list[dict[str, Any]]) -> None:
    for result in results:
        log.info("")
        log.info("=== %s ===", result["event_display_fr"])
        log.info(
            "Coteur: %d marches | FanDuel: %d | Comparables: %d",
            result["coteur_market_count"],
            result["fanduel_market_count"],
            result["comparable_market_count"],
        )
        for market in result["comparable_markets"][:8]:
            log.info(
                "  %s (%s %s)",
                market["fanduel_key"],
                market["coteur_market_type"],
                market["coteur_market_special"] or "",
            )
        if len(result["comparable_markets"]) > 8:
            log.info("  ... +%d marches comparables", len(result["comparable_markets"]) - 8)
        if result["coteur_only_markets"]:
            log.info("  Coteur seulement: %d", len(result["coteur_only_markets"]))
        if result["fanduel_only_markets"]:
            log.info("  FanDuel seulement: %d", len(result["fanduel_only_markets"]))


def run(output: Path | None = None, include_doubles: bool = True) -> Path:
    coteur = CoteurClient()
    fanduel = FanDuelClient()
    bookmaker_names = {
        int(book["id"]): normalize_bookmaker_name(book.get("nom", str(book["id"])))
        for book in coteur.get_bookmakers()
        if "id" in book
    }

    log.info("Recuperation matchs tennis sur Coteur...")
    competition_pages = coteur.list_tennis_competition_pages()
    log.info("%d page(s) competition tennis detectee(s) sur Coteur", len(competition_pages))
    coteur_matches = coteur.list_tennis_matches()
    log.info("%d match(s) tennis trouve(s) sur Coteur", len(coteur_matches))

    log.info("Recuperation matchs tennis sur FanDuel...")
    page_candidates = page_id_candidates_from_urls(competition_pages)
    active_page_ids = fanduel.discover_tennis_page_ids(page_candidates)
    log.info("%d page id tennis FanDuel actif(s): %s", len(active_page_ids), ", ".join(active_page_ids))
    fanduel_events = []
    for event in fanduel.list_tennis_events(active_page_ids):
        if event.is_doubles and not include_doubles:
            continue
        log.info("FanDuel: %s", event.name)
        fanduel_events.append(fanduel.build_event_payload(event))
    log.info("%d evenement(s) FanDuel charges", len(fanduel_events))

    results = []
    unmatched = []
    for coteur_match in coteur_matches:
        coteur_data = coteur.get_full_odds(coteur_match["renc_id"])
        fanduel_event = match_coteur_to_fanduel_event(coteur_data, fanduel_events)
        info = coteur_data.get("info") or {}
        label = f"{(info.get('teamDom') or {}).get('equipeNom', '?')} vs {(info.get('teamExt') or {}).get('equipeNom', '?')}"
        if not fanduel_event:
            log.warning("Pas de correspondance FanDuel pour %s", label)
            unmatched.append(label)
            continue
        log.info("Comparaison: %s", label)
        results.append(
            compare_match(
                coteur,
                coteur_match,
                fanduel_event,
                bookmaker_names,
                coteur_data,
            )
        )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output or OUTPUT_DIR / f"tennis_compare_{stamp}.json"
    csv_path = json_path.with_suffix(".csv")

    payload = {
        "source": "coteur_vs_fanduel",
        "sport": "tennis",
        "generated_at": datetime.now().isoformat(),
        "coteur_competition_pages": competition_pages,
        "fanduel_page_ids": list(active_page_ids),
        "coteur_match_count": len(coteur_matches),
        "fanduel_event_count": len(fanduel_events),
        "matched_count": len(results),
        "unmatched_coteur_events": unmatched,
        "results": results,
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    write_csv_rows(results, csv_path)
    print_summary(results)
    log.info("Export JSON : %s", json_path.resolve())
    log.info("Export CSV  : %s", csv_path.resolve())
    return json_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare marches tennis Coteur vs FanDuel")
    parser.add_argument("-o", "--output", type=Path, help="Fichier JSON de sortie")
    parser.add_argument("--singles-only", action="store_true", help="Ignorer les doubles")
    args = parser.parse_args()
    run(args.output, include_doubles=not args.singles_only)
