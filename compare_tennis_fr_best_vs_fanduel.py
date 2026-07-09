"""Compare meilleure cote FR (Unibet/Betclic/Winamax) vs FanDuel."""

from __future__ import annotations

import argparse
import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from betclic_client import BetclicClient
from compare_tennis_books import build_variant_map
from fanduel_client import FanDuelClient, page_id_candidates_from_urls, runner_decimal_odds
from tennis_market_mapping import (
    align_fr_outcome_to_fanduel,
    fr_compare_key_to_fanduel,
    fanduel_runner_label,
    map_fanduel_market_to_compare_key,
    players_match,
)
from unibet_client import UnibetClient
from winamax_client import WinamaxClient, WinamaxMatchLink

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("compare_fr_best_fanduel")

OUTPUT_DIR = Path(__file__).parent / "output"
FR_BOOKS = ("unibet", "betclic", "winamax")


def discover_anchor_events(
    unibet_events: list[dict[str, Any]],
    betclic_events: list[dict[str, Any]],
    winamax_links: list[WinamaxMatchLink],
) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []

    def find_anchor(home: str, away: str) -> dict[str, Any] | None:
        for item in anchors:
            if players_match(home, item["home_player"]) and players_match(away, item["away_player"]):
                return item
            if players_match(home, item["away_player"]) and players_match(away, item["home_player"]):
                return item
        return None

    def add_event(home: str, away: str, *, source: str, url: str = "", competition: str = "") -> None:
        if not home or not away:
            return
        item = find_anchor(home, away)
        if item is None:
            item = {
                "home_player": home,
                "away_player": away,
                "name": f"{home} - {away}",
                "sources": set(),
                "urls": {},
                "competition": competition,
            }
            anchors.append(item)
        item["sources"].add(source)
        if url:
            item["urls"][source] = url
        if competition and not item.get("competition"):
            item["competition"] = competition

    for event in unibet_events:
        add_event(
            event.get("home", ""),
            event.get("away", ""),
            source="unibet",
            url=event.get("url", ""),
            competition=event.get("competition", ""),
        )
    for event in betclic_events:
        add_event(
            event.get("home_player", ""),
            event.get("away_player", ""),
            source="betclic",
            url=event.get("url", ""),
            competition=event.get("competition", ""),
        )
    for link in winamax_links:
        add_event(
            link.home_player,
            link.away_player,
            source="winamax",
            url=link.url,
            competition=link.competition,
        )
    return sorted(anchors, key=lambda item: item["name"])


def build_best_fr_variant_map(book_events: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for bookmaker, event in book_events.items():
        for key, market in build_variant_map(bookmaker, event).items():
            existing = best.get(key)
            if not existing:
                best[key] = {
                    "compare_key": key,
                    "market_family": market["market_family"],
                    "market_label_raw": market["market_label_raw"],
                    "is_advanced": market.get("market_family", "") in {
                        "aces_total",
                        "aces_player",
                        "breaks_total",
                        "breaks_player",
                        "first_break",
                        "tie_break_match",
                        "tie_break_set",
                    },
                    "outcomes": {},
                }
            for outcome, odds in market["outcomes"].items():
                current = best[key]["outcomes"].get(outcome)
                if current is None or float(odds) > float(current["odds"]):
                    best[key]["outcomes"][outcome] = {
                        "odds": float(odds),
                        "bookmaker": bookmaker,
                    }
    return best


def build_fanduel_variant_map(event: dict[str, Any]) -> dict[str, dict[str, Any]]:
    variant_map: dict[str, dict[str, Any]] = {}
    home = event.get("home_player", "")
    away = event.get("away_player", "")
    for market in event.get("markets", []):
        compare_key = map_fanduel_market_to_compare_key(market)
        if not compare_key:
            continue
        outcomes: dict[str, float] = {}
        for runner in market.get("runners", []):
            if runner.get("runnerStatus") not in (None, "ACTIVE"):
                continue
            odds = runner_decimal_odds(runner)
            if odds is None:
                continue
            label = fanduel_runner_label(
                compare_key,
                str(runner.get("runnerName", "")),
                home,
                away,
            )
            outcomes[label] = float(odds)
        if not outcomes:
            continue
        variant_map[compare_key] = {
            "compare_key": compare_key,
            "market_name": market.get("marketName", ""),
            "outcomes": outcomes,
        }
    return variant_map


def compare_best_fr_to_fanduel(
    anchor: dict[str, Any],
    book_events: dict[str, dict[str, Any]],
    fanduel_event: dict[str, Any],
) -> dict[str, Any]:
    home = anchor["home_player"]
    away = anchor["away_player"]
    best_fr = build_best_fr_variant_map(book_events)
    fanduel_variants = build_fanduel_variant_map(fanduel_event)

    comparable_markets = []
    fr_only = []
    for fr_key, fr_market in best_fr.items():
        fd_key = fr_compare_key_to_fanduel(fr_key)
        fanduel_market = fanduel_variants.get(fd_key)
        if not fanduel_market:
            fr_only.append({"compare_key": fr_key, "market_family": fr_market["market_family"]})
            continue

        outcome_rows = []
        for fr_outcome, fr_payload in fr_market["outcomes"].items():
            aligned_fr = align_fr_outcome_to_fanduel(fr_outcome, fr_key, home, away)
            fd_outcome = None
            fd_odds = None
            for candidate_label, candidate_odds in fanduel_market["outcomes"].items():
                aligned_fd = align_fr_outcome_to_fanduel(candidate_label, fd_key, home, away)
                if aligned_fr == aligned_fd or aligned_fr == candidate_label or fr_outcome == candidate_label:
                    fd_outcome = candidate_label
                    fd_odds = float(candidate_odds)
                    break
            if fd_odds is None:
                continue
            fr_odds = float(fr_payload["odds"])
            outcome_rows.append(
                {
                    "outcome": aligned_fr,
                    "best_fr_odds": fr_odds,
                    "best_fr_bookmaker": fr_payload["bookmaker"],
                    "fanduel_odds": fd_odds,
                    "price_delta": fr_odds - fd_odds,
                    "best_side": "fr" if fr_odds > fd_odds else "fanduel",
                    "fr_books": sorted(
                        {
                            payload["bookmaker"]
                            for payload in fr_market["outcomes"].values()
                        }
                    ),
                }
            )
        if not outcome_rows:
            continue
        comparable_markets.append(
            {
                "compare_key": fr_key,
                "fanduel_compare_key": fd_key,
                "market_family": fr_market["market_family"],
                "is_advanced": fr_market["is_advanced"],
                "fr_market_label": fr_market["market_label_raw"],
                "fanduel_market_label": fanduel_market["market_name"],
                "outcomes_compared": outcome_rows,
            }
        )

    return {
        "event": anchor["name"],
        "event_display_fr": f"{home} vs {away}",
        "sources": sorted(anchor.get("sources", [])),
        "unibet_url": anchor.get("urls", {}).get("unibet", ""),
        "betclic_url": anchor.get("urls", {}).get("betclic", ""),
        "winamax_url": anchor.get("urls", {}).get("winamax", ""),
        "fanduel_event_id": fanduel_event.get("event_id", ""),
        "fr_book_count": len(book_events),
        "comparable_market_count": len(comparable_markets),
        "advanced_comparable_count": sum(1 for item in comparable_markets if item["is_advanced"]),
        "fr_higher_than_fanduel_count": sum(
            1
            for market in comparable_markets
            for outcome in market["outcomes_compared"]
            if outcome["best_side"] == "fr"
        ),
        "comparable_markets": comparable_markets,
        "fr_only_markets": fr_only,
    }


def write_csv_rows(results: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "event",
                "compare_key",
                "is_advanced",
                "outcome",
                "best_fr_odds",
                "best_fr_bookmaker",
                "fanduel_odds",
                "price_delta",
                "best_side",
            ],
        )
        writer.writeheader()
        for result in results:
            for market in result["comparable_markets"]:
                for outcome in market["outcomes_compared"]:
                    writer.writerow(
                        {
                            "event": result["event_display_fr"],
                            "compare_key": market["compare_key"],
                            "is_advanced": market["is_advanced"],
                            "outcome": outcome["outcome"],
                            "best_fr_odds": outcome["best_fr_odds"],
                            "best_fr_bookmaker": outcome["best_fr_bookmaker"],
                            "fanduel_odds": outcome["fanduel_odds"],
                            "price_delta": outcome["price_delta"],
                            "best_side": outcome["best_side"],
                        }
                    )


def find_event_by_players(
    home: str,
    away: str,
    events: list[dict[str, Any]],
    *,
    home_key: str = "home_player",
    away_key: str = "away_player",
) -> dict[str, Any] | None:
    for event in events:
        event_home = str(event.get(home_key, event.get("home", "")))
        event_away = str(event.get(away_key, event.get("away", "")))
        if players_match(home, event_home) and players_match(away, event_away):
            return event
        if players_match(home, event_away) and players_match(away, event_home):
            return event
    return None


def run(output: Path | None = None) -> Path:
    unibet = UnibetClient()
    betclic = BetclicClient()
    winamax = WinamaxClient()
    fanduel = FanDuelClient()

    log.info("Decouverte matchs Unibet...")
    unibet_meta = unibet.list_singles_tennis_events()
    log.info("%d match(s) Unibet", len(unibet_meta))

    log.info("Decouverte matchs Betclic...")
    betclic_links = betclic.list_tennis_match_links()
    betclic_events = []
    for link in betclic_links:
        try:
            betclic_events.append(betclic.build_event_payload(link.url))
            log.info(
                "Betclic: %s (%d SSR + %d gRPC)",
                betclic_events[-1]["name"],
                betclic_events[-1]["ssr_market_count"],
                betclic_events[-1].get("grpc_market_count", 0),
            )
        except Exception as exc:
            log.warning("Betclic ignore %s: %s", link.url, exc)

    log.info("Decouverte matchs Winamax...")
    winamax_links = winamax.list_singles_tennis_matches()
    log.info("%d match(s) Winamax", len(winamax_links))

    anchors = discover_anchor_events(unibet_meta, betclic_events, winamax_links)
    log.info("%d evenement(s) ancres (union FR)", len(anchors))

    log.info("Decouverte matchs FanDuel...")
    page_ids = fanduel.discover_tennis_page_ids(("wimbledon", "wimbledon-simples-hommes", "wimbledon-simples-dames"))
    fanduel_events = [fanduel.build_event_payload(event) for event in fanduel.list_tennis_events(page_ids)]
    log.info("%d evenement(s) FanDuel", len(fanduel_events))

    winamax_payloads = {
        event["match_id"]: event
        for event in winamax.build_event_payloads(winamax_links)
    }

    unibet_payloads: list[dict[str, Any]] = []
    for meta in unibet_meta:
        try:
            unibet_payloads.append(unibet.build_event_payload(meta))
            log.info("Unibet: %s (%d marches)", meta.get("name", ""), unibet_payloads[-1]["market_count"])
        except Exception as exc:
            log.warning("Unibet ignore %s: %s", meta.get("url", ""), exc)

    results = []
    unmatched = []
    for anchor in anchors:
        home = anchor["home_player"]
        away = anchor["away_player"]
        label = f"{home} vs {away}"

        book_events: dict[str, dict[str, Any]] = {}

        unibet_event = find_event_by_players(home, away, unibet_payloads)
        if unibet_event and unibet_event.get("markets"):
            book_events["unibet"] = unibet_event

        betclic_event = find_event_by_players(home, away, betclic_events)
        if betclic_event:
            book_events["betclic"] = betclic_event

        winamax_link = find_event_by_players(
            home,
            away,
            [{"home_player": link.home_player, "away_player": link.away_player, "match_id": link.match_id} for link in winamax_links],
        )
        if winamax_link:
            payload = winamax_payloads.get(str(winamax_link.get("match_id", "")))
            if payload:
                book_events["winamax"] = payload

        fanduel_event = find_event_by_players(home, away, fanduel_events)
        if not fanduel_event:
            log.warning("Pas de FanDuel pour %s", label)
            unmatched.append(label)
            continue
        if len(book_events) < 1:
            continue

        log.info("Comparaison best-FR vs FanDuel: %s (%s)", label, ",".join(book_events))
        results.append(compare_best_fr_to_fanduel(anchor, book_events, fanduel_event))

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output or OUTPUT_DIR / f"tennis_fr_best_vs_fanduel_{stamp}.json"
    csv_path = json_path.with_suffix(".csv")
    payload = {
        "source": "best_fr_vs_fanduel",
        "generated_at": datetime.now().isoformat(),
        "anchor_count": len(anchors),
        "matched_count": len(results),
        "unmatched_fanduel": unmatched,
        "notes": {
            "best_fr_rule": "max(unibet, betclic, winamax) par issue",
            "winamax_aces": "Aucun marche aces detecte sur les matchs actuels; normalisation prete si disponible.",
            "betclic_grpc": "Requetes gRPC avec headers X-BG-*; categories chargees hors SSR.",
            "unibet_live": "Matchs live (/paris-en-direct/) inclus dans la decouverte Unibet.",
        },
        "results": results,
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    write_csv_rows(results, csv_path)

    for result in results:
        log.info(
            "%s | comparables=%d | FR>FD=%d | sources=%s",
            result["event_display_fr"],
            result["comparable_market_count"],
            result["fr_higher_than_fanduel_count"],
            ",".join(result["sources"]),
        )
    log.info("Export JSON : %s", json_path)
    log.info("Export CSV  : %s", csv_path)
    return json_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare meilleure cote FR vs FanDuel")
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()
    run(args.output)
