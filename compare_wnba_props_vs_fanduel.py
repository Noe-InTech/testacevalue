"""Compare stats joueuses WNBA — books FR vs FanDuel.

Pipeline séparé du tennis : ne modifie pas compare_tennis_*.
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from basketball_books_mapping import (
    BOOK_NORMALIZERS,
    is_wnba_player_prop_label,
    normalized_market_to_dict,
)
from basketball_constants import BOOK_LABELS
from basketball_market_mapping import (
    align_fr_outcome_to_fanduel,
    build_double_double_key,
    build_player_prop_key,
    fanduel_player_prop_runner_outcome,
    is_comparable_player_prop_key,
    map_fanduel_market_to_compare_key,
    resolve_roster_player,
    strip_accents,
    tier_threshold_to_ou_line,
    FD_TIER_MARKET_SPECS,
)
from betclic_basketball_client import BetclicBasketballClient
from fanduel_basketball_client import FanDuelBasketballClient
from fanduel_client import format_american_moneyline, format_french_decimal, runner_fanduel_price_bundle
from tennis_market_mapping import players_match
from unibet_basketball_client import UnibetBasketballClient
from winamax_basketball_client import WinamaxBasketballClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("compare_wnba")

OUTPUT_DIR = Path(__file__).parent / "output"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def teams_match(home_a: str, away_a: str, home_b: str, away_b: str) -> bool:
    return (
        players_match(home_a, home_b) and players_match(away_a, away_b)
    ) or (
        players_match(home_a, away_b) and players_match(away_a, home_b)
    )


def build_best_fr_player_props_map(
    book_events: dict[str, dict[str, Any]],
    *,
    roster: list[str],
) -> dict[str, dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for bookmaker, event in book_events.items():
        normalizer = BOOK_NORMALIZERS[bookmaker]
        for market in event.get("markets", []):
            label = str(market.get("label", "")).strip()
            if not is_wnba_player_prop_label(label):
                continue
            outcomes = [(str(raw), odds) for raw, odds in market.get("outcomes", [])]
            for item in normalizer(label, outcomes, roster):
                payload = normalized_market_to_dict(item, roster)
                for outcome, odds in payload["outcomes"].items():
                    aligned = align_fr_outcome_to_fanduel(outcome, item.compare_key)
                    slot = best.setdefault(
                        item.compare_key,
                        {
                            "compare_key": item.compare_key,
                            "market_family": item.market_family,
                            "market_label_raw": item.market_label_raw,
                            "player_name": item.player_name,
                            "line": item.line,
                            "outcomes": {},
                        },
                    )
                    current = slot["outcomes"].get(aligned)
                    if current is None or float(odds) > float(current["odds"]):
                        slot["outcomes"][aligned] = {
                            "odds": float(odds),
                            "bookmaker": bookmaker,
                            "bookmaker_label": BOOK_LABELS.get(bookmaker, bookmaker),
                            "raw_outcome": outcome,
                        }
    return best


def build_fanduel_player_props_map(
    fanduel_event: dict[str, Any] | None,
    *,
    roster: list[str],
) -> dict[str, dict[str, Any]]:
    if not fanduel_event:
        return {}
    variant_map: dict[str, dict[str, Any]] = {}

    def store_outcome(compare_key: str, market_label: str, outcome: str, bundle: dict[str, Any]) -> None:
        slot = variant_map.setdefault(
            compare_key,
            {
                "compare_key": compare_key,
                "market_label": market_label,
                "outcomes": {},
            },
        )
        slot["outcomes"][outcome] = bundle

    for market in fanduel_event.get("markets", []):
        market_label = str(market.get("marketName", ""))
        compare_key = map_fanduel_market_to_compare_key(market, roster=roster)
        if compare_key:
            for runner in market.get("runners", []):
                if runner.get("runnerStatus") not in (None, "ACTIVE"):
                    continue
                bundle = runner_fanduel_price_bundle(runner)
                if bundle.get("decimal_fr") is None:
                    continue
                runner_name = str(runner.get("runnerName", "")).strip()
                store_outcome(
                    compare_key,
                    market_label,
                    fanduel_player_prop_runner_outcome(runner_name),
                    bundle,
                )
            continue

        lower = strip_accents(market_label)
        if lower == "to record a double double":
            for runner in market.get("runners", []):
                if runner.get("runnerStatus") not in (None, "ACTIVE"):
                    continue
                bundle = runner_fanduel_price_bundle(runner)
                if bundle.get("decimal_fr") is None:
                    continue
                player_name = resolve_roster_player(str(runner.get("runnerName", "")).strip(), roster)
                store_outcome(build_double_double_key(player_name), market_label, "Yes", bundle)
            continue

        for _family, pattern in FD_TIER_MARKET_SPECS:
            match = pattern.search(market_label)
            if not match:
                continue
            line = tier_threshold_to_ou_line(match.group(1))
            for runner in market.get("runners", []):
                if runner.get("runnerStatus") not in (None, "ACTIVE"):
                    continue
                bundle = runner_fanduel_price_bundle(runner)
                if bundle.get("decimal_fr") is None:
                    continue
                player_name = resolve_roster_player(str(runner.get("runnerName", "")).strip(), roster)
                store_outcome(
                    build_player_prop_key(_family, player_name, line),
                    market_label,
                    "Over",
                    bundle,
                )
            break

    return variant_map


def format_ligne_props_fr(row: dict[str, Any]) -> str:
    compare_key = str(row.get("compare_key", ""))
    parts = compare_key.split("|")
    family = parts[0] if parts else ""
    player = str(row.get("player_name") or (parts[1].replace("_", " ").title() if len(parts) >= 2 else ""))
    line = parts[2].replace(".", ",") if len(parts) >= 3 else ""
    issue = str(row.get("outcome", ""))
    if issue in {"Over", "Under"}:
        issue = "Plus" if issue == "Over" else "Moins"
    if issue == "Yes":
        issue = "Oui"
    labels = {
        "points_player": "points",
        "rebounds_player": "rebonds",
        "assists_player": "passes",
        "threes_made_player": "3pts",
        "blocks_player": "contres",
        "steals_player": "interceptions",
        "turnovers_player": "pertes de balle",
        "points_rebounds_player": "pts+reb",
        "points_assists_player": "pts+ast",
        "rebounds_assists_player": "reb+ast",
        "pra_player": "pts+reb+ast",
        "double_double_player": "double-double",
    }
    stat = labels.get(family, family)
    if family == "double_double_player" and player:
        return f"{issue} double-double — {player}"
    if player and line:
        return f"{issue} de {line} {stat} — {player}"
    return str(row.get("fr_market_label") or compare_key)


def compare_normalized_props(
    fr_map: dict[str, dict[str, Any]],
    fd_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for compare_key, fr_market in fr_map.items():
        if not is_comparable_player_prop_key(compare_key):
            continue
        fd_market = fd_map.get(compare_key)
        if not fd_market:
            continue
        for outcome, fr_payload in fr_market["outcomes"].items():
            fd_bundle = fd_market["outcomes"].get(outcome)
            if not fd_bundle or fd_bundle.get("decimal_fr") is None:
                continue
            row = {
                "compare_key": compare_key,
                "market_family": fr_market["market_family"],
                "player_name": fr_market.get("player_name", ""),
                "outcome": outcome,
                "fr_market_label": fr_market["market_label_raw"],
                "fanduel_market_label": fd_market.get("market_label", ""),
                "best_fr_odds": fr_payload["odds"],
                "best_fr_bookmaker": fr_payload["bookmaker_label"],
                "cote_fr": format_french_decimal(float(fr_payload["odds"])),
                "bookmaker_fr": fr_payload["bookmaker_label"],
                "cote_us_fanduel_ml": format_american_moneyline(fd_bundle.get("american")),
                "cote_fr_fanduel": format_french_decimal(float(fd_bundle["decimal_fr"])),
                "fanduel_odds": float(fd_bundle.get("decimal_raw") or fd_bundle["decimal_fr"]),
            }
            row["ligne_props_fr"] = format_ligne_props_fr(row)
            rows.append(row)
    return rows


def merge_roster(*rosters: list[str] | None) -> list[str]:
    garbage = {"joueur", "equipe", "player", "team"}
    names: list[str] = []
    for roster in rosters:
        if not roster:
            continue
        for name in roster:
            text = str(name).strip()
            lower = text.lower()
            if not text or lower in garbage or lower.endswith(" gagne &"):
                continue
            if text not in names:
                names.append(text)
    return names


def discover_anchors(
    *,
    unibet_events: list[Any],
    betclic_links: list[Any],
    winamax_links: list[Any],
    fanduel_events: list[Any],
) -> list[dict[str, Any]]:
    anchors: dict[str, dict[str, Any]] = {}

    def anchor_key(home: str, away: str) -> str:
        return f"{home.lower()}|{away.lower()}"

    def ensure_anchor(home: str, away: str) -> dict[str, Any]:
        key = anchor_key(home, away)
        if key not in anchors:
            anchors[key] = {
                "home_team": home,
                "away_team": away,
                "match": f"{home} vs {away}",
                "sources": set(),
                "urls": {},
                "unibet_event_id": None,
                "betclic_match_id": None,
                "winamax_match_id": None,
                "fanduel_event_id": None,
            }
        return anchors[key]

    for event in unibet_events:
        anchor = ensure_anchor(event.home_team, event.away_team)
        anchor["sources"].add("unibet")
        anchor["urls"]["unibet"] = event.url
        anchor["unibet_event_id"] = event.event_id

    for link in betclic_links:
        anchor = ensure_anchor(link.home_team, link.away_team)
        anchor["sources"].add("betclic")
        anchor["urls"]["betclic"] = link.url
        anchor["betclic_match_id"] = link.match_id

    for link in winamax_links:
        anchor = ensure_anchor(link.home_team, link.away_team)
        anchor["sources"].add("winamax")
        anchor["urls"]["winamax"] = link.url
        anchor["winamax_match_id"] = link.match_id

    for event in fanduel_events:
        matched_key = None
        for key, anchor in anchors.items():
            if teams_match(
                anchor["home_team"],
                anchor["away_team"],
                event.home_team,
                event.away_team,
            ):
                matched_key = key
                break
        if matched_key is None:
            anchor = ensure_anchor(event.home_team, event.away_team)
            matched_key = anchor_key(event.home_team, event.away_team)
        anchor = anchors[matched_key]
        anchor["sources"].add("fanduel")
        anchor["fanduel_event_id"] = event.event_id

    return list(anchors.values())


def run_compare(*, match_filter: str = "") -> dict[str, Any]:
    unibet = UnibetBasketballClient()
    betclic = BetclicBasketballClient()
    winamax = WinamaxBasketballClient(fetch_timeout=25)
    fanduel = FanDuelBasketballClient()

    unibet_events = unibet.list_wnba_events()
    betclic_links = betclic.list_wnba_matches()
    winamax_links = winamax.list_wnba_matches()
    fanduel_events = fanduel.list_wnba_events()
    anchors = discover_anchors(
        unibet_events=unibet_events,
        betclic_links=betclic_links,
        winamax_links=winamax_links,
        fanduel_events=fanduel_events,
    )
    if match_filter:
        needle = match_filter.strip().lower()
        anchors = [anchor for anchor in anchors if needle in anchor["match"].lower()]

    results: list[dict[str, Any]] = []
    comparable_rows: list[dict[str, Any]] = []
    fr_only_rows: list[dict[str, Any]] = []
    fd_only_rows: list[dict[str, Any]] = []

    for anchor in anchors:
        book_events: dict[str, dict[str, Any]] = {}

        unibet_event = next(
            (item for item in unibet_events if item.event_id == anchor.get("unibet_event_id")),
            None,
        )
        if unibet_event:
            book_events["unibet"] = unibet.build_event_payload(unibet_event)

        betclic_link = next(
            (item for item in betclic_links if item.match_id == anchor.get("betclic_match_id")),
            None,
        )
        if betclic_link:
            book_events["betclic"] = betclic.build_event_payload(betclic_link)

        winamax_link = next(
            (item for item in winamax_links if item.match_id == anchor.get("winamax_match_id")),
            None,
        )
        if winamax_link:
            book_events["winamax"] = winamax.build_event_payload(winamax_link)

        roster = merge_roster(
            book_events.get("winamax", {}).get("roster"),
            book_events.get("unibet", {}).get("roster"),
            book_events.get("betclic", {}).get("roster"),
            [anchor["home_team"], anchor["away_team"]],
        )

        fanduel_payload = None
        if anchor.get("fanduel_event_id"):
            event = next(
                (item for item in fanduel_events if item.event_id == anchor["fanduel_event_id"]),
                None,
            )
            if event:
                fanduel_payload = fanduel.build_event_payload(event)

        fr_map = build_best_fr_player_props_map(book_events, roster=roster)
        fd_map = build_fanduel_player_props_map(fanduel_payload, roster=roster)
        comparable = compare_normalized_props(fr_map, fd_map)

        for compare_key, fr_market in fr_map.items():
            fd_market = fd_map.get(compare_key)
            for outcome, fr_payload in fr_market["outcomes"].items():
                if fd_market and outcome in fd_market.get("outcomes", {}):
                    continue
                row = {
                    "match": anchor["match"],
                    "compare_key": compare_key,
                    "outcome": outcome,
                    "best_fr_odds": fr_payload["odds"],
                    "best_fr_bookmaker": fr_payload["bookmaker_label"],
                    "fr_market_label": fr_market["market_label_raw"],
                }
                row["ligne_props_fr"] = format_ligne_props_fr(row)
                fr_only_rows.append(row)

        for compare_key, fd_market in fd_map.items():
            fr_market = fr_map.get(compare_key)
            for outcome, fd_bundle in fd_market.get("outcomes", {}).items():
                if fr_market and outcome in fr_market.get("outcomes", {}):
                    continue
                row = {
                    "match": anchor["match"],
                    "compare_key": compare_key,
                    "outcome": outcome,
                    "fanduel_market_label": fd_market.get("market_label", ""),
                    "cote_fr_fanduel": format_french_decimal(float(fd_bundle["decimal_fr"])),
                    "cote_us_fanduel_ml": format_american_moneyline(fd_bundle.get("american")),
                }
                row["ligne_props_fr"] = format_ligne_props_fr(row)
                fd_only_rows.append(row)

        result = {
            "match": anchor["match"],
            "sources": sorted(anchor["sources"]),
            "fanduel_event_id": anchor.get("fanduel_event_id"),
            "comparable_count": len(comparable),
            "fr_prop_market_count": len(fr_map),
            "fd_prop_market_count": len(fd_map),
            "comparables": comparable,
        }
        results.append(result)
        comparable_rows.extend({**row, "match": anchor["match"]} for row in comparable)

    return {
        "source": "wnba_player_props_comparable",
        "generated_at": utc_now(),
        "anchors_total": len(anchors),
        "matches_done": len(results),
        "comparable_count": len(comparable_rows),
        "fr_only_count": len(fr_only_rows),
        "fd_only_count": len(fd_only_rows),
        "results": results,
        "comparables": comparable_rows,
        "fr_only_comparables": fr_only_rows,
        "fd_only_comparables": fd_only_rows,
        "notes": [
            "Pipeline WNBA séparé du tennis.",
            "Référence US: FanDuel (props joueuse O/U).",
            "Books FR: Unibet, Betclic, Winamax — meilleure cote par compare_key.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare props WNBA FR vs FanDuel")
    parser.add_argument("--match", default="", help="Filtre texte sur le match")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=OUTPUT_DIR / "wnba_props_compare.json",
    )
    args = parser.parse_args()

    payload = run_compare(match_filter=args.match)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(
        "WNBA compare terminé — %d match(s), %d comparable(s), %d FR seul, %d FD seul",
        payload["matches_done"],
        payload["comparable_count"],
        payload["fr_only_count"],
        payload["fd_only_count"],
    )


if __name__ == "__main__":
    main()
