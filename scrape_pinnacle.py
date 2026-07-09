"""Exporte les marchés Pinnacle foot via l'API invitée du front web."""

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from pinnacle_guest_client import PinnacleGuestClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("scrape_pinnacle")

OUTPUT_DIR = Path(__file__).parent / "output"


def american_to_decimal(price: int | float | None) -> float | None:
    if price in (None, 0):
        return None
    price = float(price)
    if price > 0:
        return round(1 + price / 100.0, 4)
    return round(1 + 100.0 / abs(price), 4)


def period_label(period: int) -> str:
    labels = {
        0: "Match",
        1: "1re mi-temps",
        2: "2e mi-temps",
        6: "Temps reglementaire",
        8: "Qualification",
    }
    return labels.get(period, f"Periode {period}")


def build_matchup_name_map(related_matchups: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {int(item["id"]): item for item in related_matchups if "id" in item}


def market_group_label(market: dict[str, Any], matchup: dict[str, Any]) -> str:
    market_type = market.get("type", "")
    special = matchup.get("special") or {}
    if market_type == "moneyline":
        if special.get("description"):
            return str(special["description"])
        return "1X2" if len(market.get("prices", [])) == 3 else "Vainqueur"
    if market_type == "spread":
        return "Handicap"
    if market_type == "total":
        return "Over/Under"
    if market_type == "team_total":
        return "Total equipe"
    return market_type


def build_market_variant_label(market: dict[str, Any], matchup: dict[str, Any]) -> str:
    special = matchup.get("special") or {}
    if special.get("description"):
        return str(special["description"])
    if market.get("type") in {"total", "team_total"}:
        points = next((p.get("points") for p in market.get("prices", []) if p.get("points") is not None), None)
        if points is not None:
            return f"Ligne {points}"
    if market.get("type") == "spread":
        points = next((p.get("points") for p in market.get("prices", []) if p.get("designation") == "home"), None)
        if points is not None:
            return f"Handicap {points}"
    return period_label(int(market.get("period", 0)))


def outcome_label(price_item: dict[str, Any], matchup: dict[str, Any], root_home: str, root_away: str) -> str:
    designation = str(price_item.get("designation", ""))
    side = str(price_item.get("side", matchup.get("side", "")))
    participants = matchup.get("participants") or []
    participant_id = price_item.get("participantId")

    if participant_id is not None:
        for participant in participants:
            if participant.get("id") == participant_id:
                return str(participant.get("name", participant_id))

    if designation == "home":
        return root_home
    if designation == "away":
        return root_away
    if designation == "draw":
        return "Nul"
    if designation == "over":
        if side == "home":
            return f"{root_home} Over"
        if side == "away":
            return f"{root_away} Over"
        return "Over"
    if designation == "under":
        if side == "home":
            return f"{root_home} Under"
        if side == "away":
            return f"{root_away} Under"
        return "Under"
    return designation or str(participant_id or "")


def build_market_payload(
    market: dict[str, Any],
    matchup: dict[str, Any],
    root_home: str,
    root_away: str,
) -> dict[str, Any]:
    prices = []
    for item in market.get("prices", []):
        prices.append(
            {
                "designation": item.get("designation"),
                "participant_id": item.get("participantId"),
                "points": item.get("points"),
                "american_odds": item.get("price"),
                "decimal_odds": american_to_decimal(item.get("price")),
                "outcome": outcome_label(item, matchup, root_home, root_away),
            }
        )

    return {
        "matchup_id": market.get("matchupId"),
        "market_key": market.get("key"),
        "market_type": market.get("type"),
        "period": market.get("period"),
        "period_label": period_label(int(market.get("period", 0))),
        "status": market.get("status"),
        "is_alternate": bool(market.get("isAlternate", False)),
        "category": (matchup.get("special") or {}).get("category"),
        "description": (matchup.get("special") or {}).get("description"),
        "market_group_label": market_group_label(market, matchup),
        "variant_label": build_market_variant_label(market, matchup),
        "prices": prices,
        "limits": market.get("limits", []),
        "cutoff_at": market.get("cutoffAt"),
        "version": market.get("version"),
    }


def is_main_event(matchup: dict[str, Any]) -> bool:
    participants = matchup.get("participants") or []
    if matchup.get("parentId") is not None:
        return False
    if matchup.get("type") != "matchup":
        return False
    return len(participants) == 2


def build_event_payload(client: PinnacleGuestClient, matchup: dict[str, Any]) -> dict[str, Any]:
    related_matchups = client.get_related_matchups(int(matchup["id"]))
    related_markets = client.get_related_markets(int(matchup["id"]))
    matchup_map = build_matchup_name_map(related_matchups)

    home_team = str((matchup.get("participants") or [])[0].get("name", ""))
    away_team = str((matchup.get("participants") or [])[1].get("name", ""))

    markets = []
    for market in related_markets:
        market_matchup = matchup_map.get(int(market.get("matchupId", matchup["id"])), matchup)
        markets.append(build_market_payload(market, market_matchup, home_team, away_team))

    markets.sort(
        key=lambda item: (
            item["period"],
            item["market_group_label"],
            item["variant_label"],
            item["market_key"],
        )
    )

    return {
        "event": f"{home_team} vs {away_team}",
        "matchup_id": matchup["id"],
        "league_id": (matchup.get("league") or {}).get("id"),
        "league_name": (matchup.get("league") or {}).get("name"),
        "group": (matchup.get("league") or {}).get("group"),
        "start_time": matchup.get("startTime"),
        "home_team": home_team,
        "away_team": away_team,
        "market_count": len(markets),
        "markets": markets,
    }


def export_soccer(output: Path | None = None) -> Path:
    client = PinnacleGuestClient()
    leagues = client.list_active_soccer_leagues()
    log.info("%d ligue(s) foot active(s) sur Pinnacle", len(leagues))

    events = []
    seen_matchups: set[int] = set()
    for league in leagues:
        matchups = client.get_league_matchups(league.id)
        main_events = [matchup for matchup in matchups if is_main_event(matchup)]
        log.info(
            "Ligue Pinnacle: %s | %s (%d event(s))",
            league.group,
            league.name,
            len(main_events),
        )
        for matchup in main_events:
            matchup_id = int(matchup["id"])
            if matchup_id in seen_matchups:
                continue
            seen_matchups.add(matchup_id)
            event = build_event_payload(client, matchup)
            events.append(event)
            log.info("%s : %d marches", event["event"], event["market_count"])

    events.sort(key=lambda item: (item["start_time"], item["event"]))

    payload = {
        "source": "pinnacle_guest_api",
        "competition": "All soccer leagues",
        "group": "All groups",
        "generated_at": datetime.now().isoformat(),
        "league_count": len(leagues),
        "event_count": len(events),
        "events": events,
    }

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output or OUTPUT_DIR / f"pinnacle_soccer_{stamp}.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    log.info("Export JSON : %s", json_path.resolve())
    return json_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export Pinnacle soccer via guest API")
    parser.add_argument("-o", "--output", type=Path, help="Fichier JSON de sortie")
    args = parser.parse_args()
    export_soccer(args.output)
