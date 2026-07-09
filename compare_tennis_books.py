"""Compare les marchés tennis Unibet vs Betclic vs Winamax."""

from __future__ import annotations

import argparse
import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from betclic_client import BetclicClient
from tennis_books_mapping import (
    is_advanced_compare_key,
    normalize_betclic_market,
    normalize_unibet_market,
    normalize_winamax_market,
    normalized_market_to_dict,
)
from tennis_market_mapping import players_match
from unibet_client import UnibetClient
from winamax_client import WinamaxClient, WinamaxMatchLink

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("compare_tennis_books")

OUTPUT_DIR = Path(__file__).parent / "output"
BOOK_NORMALIZERS = {
    "unibet": normalize_unibet_market,
    "betclic": normalize_betclic_market,
    "winamax": normalize_winamax_market,
}


def build_variant_map(
    bookmaker: str,
    event: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    home = event.get("home_player", "")
    away = event.get("away_player", "")
    variant_map: dict[str, dict[str, Any]] = {}
    normalizer = BOOK_NORMALIZERS[bookmaker]

    for market in event.get("markets", []):
        label = str(market.get("label", ""))
        outcomes = [(str(raw), odds) for raw, odds in market.get("outcomes", [])]
        normalized = normalizer(label, outcomes, home, away)

        for item in normalized:
            existing = variant_map.get(item.compare_key)
            payload = normalized_market_to_dict(item, home, away)
            if existing and len(existing["outcomes"]) >= len(payload["outcomes"]):
                continue
            variant_map[item.compare_key] = payload
    return variant_map


def match_book_event(
    anchor_event: dict[str, Any],
    candidate_events: list[dict[str, Any]],
) -> dict[str, Any] | None:
    home = anchor_event.get("home_player", "")
    away = anchor_event.get("away_player", "")
    for event in candidate_events:
        book_home = event.get("home_player", "")
        book_away = event.get("away_player", "")
        if players_match(home, book_home) and players_match(away, book_away):
            return event
        if players_match(home, book_away) and players_match(away, book_home):
            return event
    return None


def _best_bookmaker(odds_by_book: dict[str, float]) -> str:
    return max(odds_by_book.items(), key=lambda item: item[1])[0]


def compare_events(
    unibet_event: dict[str, Any],
    betclic_event: dict[str, Any] | None,
    winamax_event: dict[str, Any] | None,
) -> dict[str, Any]:
    book_events = {"unibet": unibet_event}
    if betclic_event:
        book_events["betclic"] = betclic_event
    if winamax_event:
        book_events["winamax"] = winamax_event

    variant_maps = {
        bookmaker: build_variant_map(bookmaker, event)
        for bookmaker, event in book_events.items()
    }
    unibet_variants = variant_maps["unibet"]

    comparable_markets = []
    unibet_only = []
    betclic_only = []
    winamax_only = []

    for key, unibet_market in unibet_variants.items():
        present_books = {
            bookmaker: variant_maps[bookmaker][key]
            for bookmaker in variant_maps
            if key in variant_maps[bookmaker]
        }
        if len(present_books) < 2:
            unibet_only.append(
                {
                    "compare_key": key,
                    "market_family": unibet_market["market_family"],
                    "market_label_raw": unibet_market["market_label_raw"],
                    "is_advanced": is_advanced_compare_key(key),
                }
            )
            continue

        common_labels = sorted(
            set.intersection(*(set(market["outcomes"]) for market in present_books.values()))
        )
        if not common_labels:
            unibet_only.append(
                {
                    "compare_key": key,
                    "market_family": unibet_market["market_family"],
                    "reason": "no_common_outcomes",
                }
            )
            continue

        outcome_comparisons = []
        for label in common_labels:
            odds_by_book = {
                bookmaker: float(market["outcomes"][label])
                for bookmaker, market in present_books.items()
            }
            unibet_odds = odds_by_book.get("unibet", 0.0)
            betclic_odds = odds_by_book.get("betclic")
            winamax_odds = odds_by_book.get("winamax")
            outcome_comparisons.append(
                {
                    "outcome": label,
                    "unibet_odds": unibet_odds,
                    "betclic_odds": betclic_odds,
                    "winamax_odds": winamax_odds,
                    "price_delta_vs_unibet": {
                        bookmaker: odds - unibet_odds
                        for bookmaker, odds in odds_by_book.items()
                        if bookmaker != "unibet"
                    },
                    "best_bookmaker": _best_bookmaker(odds_by_book),
                }
            )

        comparable_markets.append(
            {
                "compare_key": key,
                "market_family": unibet_market["market_family"],
                "is_advanced": is_advanced_compare_key(key),
                "books_compared": sorted(present_books.keys()),
                "unibet_market_label": unibet_market["market_label_raw"],
                "betclic_market_label": present_books.get("betclic", {}).get("market_label_raw", ""),
                "winamax_market_label": present_books.get("winamax", {}).get("market_label_raw", ""),
                "outcomes_compared": outcome_comparisons,
            }
        )

    for key, betclic_market in variant_maps.get("betclic", {}).items():
        if key not in unibet_variants:
            betclic_only.append(
                {
                    "compare_key": key,
                    "market_family": betclic_market["market_family"],
                    "market_label_raw": betclic_market["market_label_raw"],
                }
            )

    for key, winamax_market in variant_maps.get("winamax", {}).items():
        if key not in unibet_variants:
            winamax_only.append(
                {
                    "compare_key": key,
                    "market_family": winamax_market["market_family"],
                    "market_label_raw": winamax_market["market_label_raw"],
                    "is_advanced": is_advanced_compare_key(key),
                }
            )

    home = unibet_event.get("home_player", "")
    away = unibet_event.get("away_player", "")
    return {
        "event": unibet_event.get("name", ""),
        "event_display_fr": f"{home} vs {away}",
        "commence_time": unibet_event.get(
            "start_date",
            (betclic_event or {}).get("start_date", (winamax_event or {}).get("start_date", "")),
        ),
        "competition": unibet_event.get(
            "competition",
            (betclic_event or {}).get("competition", (winamax_event or {}).get("competition", "")),
        ),
        "unibet_url": unibet_event.get("url", ""),
        "betclic_url": (betclic_event or {}).get("url", ""),
        "winamax_url": (winamax_event or {}).get("url", ""),
        "unibet_market_count": len(unibet_event.get("markets", [])),
        "betclic_ssr_market_count": (betclic_event or {}).get(
            "ssr_market_count", len((betclic_event or {}).get("markets", []))
        ),
        "betclic_open_market_count": (betclic_event or {}).get("open_market_count", 0),
        "winamax_market_count": (winamax_event or {}).get(
            "market_count", len((winamax_event or {}).get("markets", []))
        ),
        "betclic_categories": (betclic_event or {}).get("categories", []),
        "unibet_normalized_count": len(unibet_variants),
        "betclic_normalized_count": len(variant_maps.get("betclic", {})),
        "winamax_normalized_count": len(variant_maps.get("winamax", {})),
        "comparable_market_count": len(comparable_markets),
        "advanced_comparable_count": sum(1 for item in comparable_markets if item["is_advanced"]),
        "winamax_advanced_comparable_count": sum(
            1
            for item in comparable_markets
            if item["is_advanced"] and "winamax" in item["books_compared"]
        ),
        "comparable_markets": comparable_markets,
        "unibet_only_markets": unibet_only,
        "betclic_only_markets": betclic_only,
        "winamax_only_markets": winamax_only,
    }


def write_csv_rows(results: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "event",
                "event_display_fr",
                "compare_key",
                "market_family",
                "is_advanced",
                "books_compared",
                "outcome",
                "unibet_odds",
                "betclic_odds",
                "winamax_odds",
                "best_bookmaker",
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
                            "compare_key": market["compare_key"],
                            "market_family": market["market_family"],
                            "is_advanced": market["is_advanced"],
                            "books_compared": ",".join(market.get("books_compared", [])),
                            "outcome": outcome["outcome"],
                            "unibet_odds": outcome["unibet_odds"],
                            "betclic_odds": outcome.get("betclic_odds", ""),
                            "winamax_odds": outcome.get("winamax_odds", ""),
                            "best_bookmaker": outcome["best_bookmaker"],
                        }
                    )


def print_summary(results: list[dict[str, Any]]) -> None:
    for result in results:
        log.info("")
        log.info("=== %s ===", result["event_display_fr"])
        log.info(
            "Unibet: %d marches (%d normalises) | Betclic SSR: %d/%d | Winamax: %d (%d normalises)",
            result["unibet_market_count"],
            result["unibet_normalized_count"],
            result["betclic_ssr_market_count"],
            result["betclic_open_market_count"],
            result["winamax_market_count"],
            result["winamax_normalized_count"],
        )
        log.info(
            "Comparables: %d (avances: %d, avances avec Winamax: %d)",
            result["comparable_market_count"],
            result["advanced_comparable_count"],
            result["winamax_advanced_comparable_count"],
        )
        for market in result["comparable_markets"][:8]:
            log.info(
                "  %s (%s) [%s]",
                market["compare_key"],
                market["market_family"],
                ",".join(market.get("books_compared", [])),
            )
        if len(result["comparable_markets"]) > 8:
            log.info("  ... +%d marches comparables", len(result["comparable_markets"]) - 8)
        if result["unibet_only_markets"]:
            advanced_only = sum(1 for item in result["unibet_only_markets"] if item.get("is_advanced"))
            log.info("  Unibet seulement: %d (%d avances)", len(result["unibet_only_markets"]), advanced_only)
        if result["winamax_only_markets"]:
            advanced_only = sum(1 for item in result["winamax_only_markets"] if item.get("is_advanced"))
            log.info("  Winamax seulement: %d (%d avances)", len(result["winamax_only_markets"]), advanced_only)


def run(output: Path | None = None, max_events: int | None = None) -> Path:
    unibet = UnibetClient()
    betclic = BetclicClient()
    winamax = WinamaxClient()

    log.info("Recuperation matchs tennis Unibet...")
    unibet_events_meta = unibet.list_singles_tennis_events()
    log.info("%d match(s) simples detecte(s) sur Unibet", len(unibet_events_meta))
    if max_events is not None:
        unibet_events_meta = unibet_events_meta[:max_events]

    log.info("Recuperation matchs tennis Betclic...")
    betclic_links = betclic.list_tennis_match_links()
    log.info("%d lien(s) match Betclic detecte(s)", len(betclic_links))

    betclic_events = []
    for link in betclic_links:
        try:
            payload = betclic.build_event_payload(link.url)
            betclic_events.append(payload)
            log.info("Betclic: %s", payload["name"])
        except Exception as exc:
            log.warning("Betclic ignore %s: %s", link.url, exc)

    log.info("Recuperation matchs tennis Winamax (Socket.IO)...")
    winamax_links = winamax.list_singles_tennis_matches()
    log.info("%d match(s) simples detecte(s) sur Winamax", len(winamax_links))
    for link in winamax_links:
        log.info("Winamax listing: %s", link.title)

    results = []
    unmatched_betclic = []
    unmatched_winamax = []
    pending_comparisons: list[tuple[dict[str, Any], dict[str, Any] | None, WinamaxMatchLink | None]] = []
    matched_winamax_links = []

    for meta in unibet_events_meta:
        try:
            unibet_event = unibet.build_event_payload(meta)
        except Exception as exc:
            log.warning("Unibet ignore %s: %s", meta.get("url"), exc)
            continue

        betclic_event = match_book_event(unibet_event, betclic_events)
        winamax_link = match_book_event(
            unibet_event,
            [
                {
                    "home_player": link.home_player,
                    "away_player": link.away_player,
                    "match_id": link.match_id,
                }
                for link in winamax_links
            ],
        )
        label = f"{unibet_event.get('home_player', '?')} vs {unibet_event.get('away_player', '?')}"

        if not betclic_event:
            log.warning("Pas de correspondance Betclic pour %s", label)
            unmatched_betclic.append(label)

        matched_link = None
        if winamax_link:
            matched_link = next(
                link for link in winamax_links if link.match_id == winamax_link.get("match_id")
            )
            matched_winamax_links.append(matched_link)
        else:
            log.warning("Pas de correspondance Winamax pour %s", label)
            unmatched_winamax.append(label)

        if not betclic_event and not matched_link:
            continue

        pending_comparisons.append((unibet_event, betclic_event, matched_link))

    winamax_events_by_id = {
        event["match_id"]: event
        for event in winamax.build_event_payloads(matched_winamax_links)
    }
    for link in matched_winamax_links:
        event = winamax_events_by_id.get(link.match_id)
        if event:
            log.info("Winamax: %s (%d marches)", event["name"], event["market_count"])

    for unibet_event, betclic_event, matched_link in pending_comparisons:
        label = f"{unibet_event.get('home_player', '?')} vs {unibet_event.get('away_player', '?')}"
        winamax_event = (
            winamax_events_by_id.get(matched_link.match_id) if matched_link is not None else None
        )
        log.info("Comparaison: %s", label)
        results.append(compare_events(unibet_event, betclic_event, winamax_event))

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output or OUTPUT_DIR / f"tennis_books_compare_{stamp}.json"
    csv_path = json_path.with_suffix(".csv")

    payload = {
        "source": "unibet_vs_betclic_vs_winamax",
        "sport": "tennis",
        "generated_at": datetime.now().isoformat(),
        "notes": {
            "betclic_advanced_markets": (
                "Marches avances Betclic charges via gRPC-web (headers X-BG-*) "
                "et fusionnes avec le SSR ng-state."
            ),
            "winamax_transport": {
                "protocol": "Socket.IO v3 / Engine.IO v3",
                "endpoint": "wss://sports-eu-west-3.winamax.fr/uof-sports-server/socket.io/",
                "routes": {
                    "listing": "sport:5",
                    "match_markets": "match:{matchId}",
                },
                "advanced_markets_available": [
                    "breaks_total",
                    "breaks_player",
                    "first_break",
                    "tie_break_match",
                ],
            },
            "parions_sport": "Parions Sport en Ligne partage le front/API Unibet.",
        },
        "unibet_event_count": len(unibet_events_meta),
        "betclic_event_count": len(betclic_events),
        "winamax_event_count": len(winamax_links),
        "matched_count": len(results),
        "unmatched_unibet_betclic": unmatched_betclic,
        "unmatched_unibet_winamax": unmatched_winamax,
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
    parser = argparse.ArgumentParser(description="Compare marches tennis Unibet vs Betclic vs Winamax")
    parser.add_argument("-o", "--output", type=Path, help="Fichier JSON de sortie")
    parser.add_argument("--max-events", type=int, help="Limiter le nombre de matchs Unibet")
    args = parser.parse_args()
    run(args.output, max_events=args.max_events)
