"""Scan des marches aces tennis sur Unibet, Betclic et Winamax."""

from __future__ import annotations

import argparse
import csv
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from betclic_client import BetclicClient
from tennis_books_mapping import strip_accents
from tennis_market_mapping import players_match
from unibet_client import UnibetClient
from winamax_client import WinamaxClient, WinamaxMatchLink

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("scan_tennis_aces")

OUTPUT_DIR = Path(__file__).parent / "output"
BETCLIC_ACES_GRPC = ("ca_ten_ptss",)
BOOK_LABELS = {
    "unibet": "Unibet",
    "betclic": "Betclic",
    "winamax": "Winamax",
}
ACE_MARKET_RE = re.compile(r"(?<![a-z])aces?(?![a-z])", re.I)


def is_aces_market(label: str) -> bool:
    lower = strip_accents(label).lower()
    if "face a face" in lower or "face-a-face" in lower:
        return False
    return ACE_MARKET_RE.search(lower) is not None


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

    def add_event(
        home: str,
        away: str,
        *,
        source: str,
        url: str = "",
        competition: str = "",
    ) -> None:
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
            str(event.get("home", "")),
            str(event.get("away", "")),
            source="unibet",
            url=str(event.get("url", "")),
            competition=str(event.get("competition", "")),
        )
    for event in betclic_events:
        add_event(
            str(event.get("home_player", "")),
            str(event.get("away_player", "")),
            source="betclic",
            url=str(event.get("url", "")),
            competition=str(event.get("competition", "")),
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


def extract_ace_quotes(bookmaker: str, event: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for market in event.get("markets", []):
        label = str(market.get("label", "")).strip()
        if not label or not is_aces_market(label):
            continue
        for raw_outcome, odds in market.get("outcomes", []):
            outcome_label = str(raw_outcome).strip()
            if not outcome_label:
                continue
            parsed_odds: float | None
            try:
                parsed_odds = float(odds) if odds is not None else None
            except (TypeError, ValueError):
                parsed_odds = None
            rows.append(
                {
                    "bookmaker": bookmaker,
                    "bookmaker_label": BOOK_LABELS.get(bookmaker, bookmaker),
                    "market_label": label,
                    "outcome_label": outcome_label,
                    "odds": parsed_odds,
                }
            )
    return rows


def pick_best_quote(quotes: list[dict[str, Any]]) -> dict[str, Any] | None:
    valid = [quote for quote in quotes if quote.get("odds") is not None]
    if not valid:
        return None
    return max(valid, key=lambda quote: float(quote["odds"]))


def scan_match(
    anchor: dict[str, Any],
    book_events: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    home = anchor["home_player"]
    away = anchor["away_player"]
    all_quotes: list[dict[str, Any]] = []
    by_book: dict[str, list[dict[str, Any]]] = {}

    for bookmaker, event in book_events.items():
        quotes = extract_ace_quotes(bookmaker, event)
        by_book[bookmaker] = quotes
        for quote in quotes:
            all_quotes.append(
                {
                    **quote,
                    "match": f"{home} vs {away}",
                    "home_player": home,
                    "away_player": away,
                }
            )

    best_match = pick_best_quote(all_quotes)
    best_by_book = {
        bookmaker: pick_best_quote(quotes)
        for bookmaker, quotes in by_book.items()
        if quotes
    }

    return {
        "match": f"{home} vs {away}",
        "home_player": home,
        "away_player": away,
        "competition": anchor.get("competition", ""),
        "sources": sorted(anchor.get("sources", [])),
        "urls": anchor.get("urls", {}),
        "ace_market_count": len({quote["market_label"] for quote in all_quotes}),
        "ace_quote_count": len(all_quotes),
        "books_with_aces": sorted(by_book.keys()),
        "quotes": all_quotes,
        "best_by_book": {
            bookmaker: quote for bookmaker, quote in best_by_book.items() if quote
        },
        "best_overall": best_match,
    }


def write_csv(path: Path, results: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "match",
                "bookmaker_label",
                "market_label",
                "outcome_label",
                "odds",
                "is_best_match",
                "is_best_global",
            ],
        )
        writer.writeheader()
        global_best = pick_best_quote(
            [quote for result in results for quote in result.get("quotes", [])]
        )
        for result in results:
            match_best = result.get("best_overall")
            for quote in result.get("quotes", []):
                writer.writerow(
                    {
                        "match": result["match"],
                        "bookmaker_label": quote["bookmaker_label"],
                        "market_label": quote["market_label"],
                        "outcome_label": quote["outcome_label"],
                        "odds": quote["odds"],
                        "is_best_match": _same_quote(quote, match_best),
                        "is_best_global": _same_quote(quote, global_best),
                    }
                )


def _same_quote(left: dict[str, Any] | None, right: dict[str, Any] | None) -> bool:
    if not left or not right:
        return False
    return (
        left.get("bookmaker") == right.get("bookmaker")
        and left.get("market_label") == right.get("market_label")
        and left.get("outcome_label") == right.get("outcome_label")
        and left.get("odds") == right.get("odds")
        and left.get("match", "") == right.get("match", "")
    )


def run(output: Path | None = None) -> Path:
    unibet = UnibetClient()
    betclic = BetclicClient()
    winamax = WinamaxClient()

    log.info("Decouverte matchs Unibet...")
    unibet_meta = unibet.list_singles_tennis_events()
    log.info("%d match(s) Unibet", len(unibet_meta))

    log.info("Decouverte matchs Betclic...")
    betclic_links = betclic.list_tennis_match_links()
    betclic_events: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(betclic_links)))) as pool:
        futures = {
            pool.submit(
                betclic.build_event_payload,
                link.url,
                grpc_categories=BETCLIC_ACES_GRPC,
            ): link
            for link in betclic_links
        }
        for future in as_completed(futures):
            link = futures[future]
            try:
                payload = future.result()
                betclic_events.append(payload)
                log.info("Betclic: %s", payload["name"])
            except Exception as exc:
                log.warning("Betclic ignore %s: %s", link.url, exc)

    log.info("Decouverte matchs Winamax...")
    winamax_links = winamax.list_singles_tennis_matches()
    log.info("%d match(s) Winamax", len(winamax_links))

    anchors = discover_anchor_events(unibet_meta, betclic_events, winamax_links)
    log.info("%d match(s) ancres", len(anchors))

    unibet_payloads: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(unibet_meta)))) as pool:
        futures = {
            pool.submit(unibet.build_event_payload, meta): meta for meta in unibet_meta
        }
        for future in as_completed(futures):
            meta = futures[future]
            try:
                unibet_payloads.append(future.result())
            except Exception as exc:
                log.warning("Unibet ignore %s: %s", meta.get("url", ""), exc)

    winamax_payloads = {
        event["match_id"]: event for event in winamax.build_event_payloads(winamax_links)
    }

    results: list[dict[str, Any]] = []
    for anchor in anchors:
        home = anchor["home_player"]
        away = anchor["away_player"]
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
            [
                {
                    "home_player": link.home_player,
                    "away_player": link.away_player,
                    "match_id": link.match_id,
                }
                for link in winamax_links
            ],
        )
        if winamax_link:
            payload = winamax_payloads.get(str(winamax_link.get("match_id", "")))
            if payload:
                book_events["winamax"] = payload

        if not book_events:
            continue

        result = scan_match(anchor, book_events)
        results.append(result)
        best = result.get("best_overall")
        if best:
            log.info(
                "%s | %d cotes aces | best %.2f @ %s | %s / %s",
                result["match"],
                result["ace_quote_count"],
                float(best["odds"]),
                best["bookmaker_label"],
                best["market_label"],
                best["outcome_label"],
            )
        else:
            log.info("%s | aucun marche aces", result["match"])

    global_best = pick_best_quote([quote for result in results for quote in result.get("quotes", [])])
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output or OUTPUT_DIR / f"tennis_aces_scan_{stamp}.json"
    csv_path = json_path.with_suffix(".csv")

    payload = {
        "source": "tennis_aces_scan",
        "generated_at": datetime.now().isoformat(),
        "match_count": len(results),
        "matches_with_aces": sum(1 for result in results if result["ace_quote_count"] > 0),
        "total_ace_quotes": sum(result["ace_quote_count"] for result in results),
        "global_best": global_best,
        "results": results,
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    write_csv(csv_path, results)

    if global_best:
        log.info(
            "Meilleure cote globale : %.2f @ %s | %s | %s / %s",
            float(global_best["odds"]),
            global_best["bookmaker_label"],
            global_best.get("match", ""),
            global_best["market_label"],
            global_best["outcome_label"],
        )
    log.info("Export JSON : %s", json_path)
    log.info("Export CSV  : %s", csv_path)
    return json_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scan marches aces tennis (Unibet / Betclic / Winamax)"
    )
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()
    run(args.output)
