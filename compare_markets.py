"""Compare les marchés et cotes Coteur vs Pinnacle — Coupe du monde."""

import argparse
import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from coteur_client import CoteurClient
from market_mapping import (
    coteur_market_label,
    coteur_outcome_label,
    map_coteur_to_pinnacle,
)
from pinnacle_guest_client import PinnacleGuestClient
from scrape_coteur import (
    build_player_name_map,
    build_bookmaker_name,
    normalize_bookmaker_name,
)
from scrape_pinnacle import build_event_payload, is_main_event

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("compare")

OUTPUT_DIR = Path(__file__).parent / "output"


TEAM_ALIASES = {
    "maroc": "morocco",
    "angleterre": "england",
    "belgique": "belgium",
    "norvege": "norway",
    "suisse": "switzerland",
    "espagne": "spain",
    "argentine": "argentina",
    "allemagne": "germany",
    "bresil": "brazil",
    "pays bas": "netherlands",
    "pays-bas": "netherlands",
    "etats unis": "united states",
    "etats-unis": "united states",
    "usa": "united states",
    "coree du sud": "south korea",
    "nouvelle zelande": "new zealand",
    "cote d ivoire": "ivory coast",
    "cote d'ivoire": "ivory coast",
    "cote divoire": "ivory coast",
    "republique tcheque": "czech republic",
    "bosnie-herzegovine": "bosnia and herzegovina",
    "iles cap-vert": "cape verde",
    "congo dr": "dr congo",
    "arabie saoudite": "saudi arabia",
}


def normalize_team(name: str) -> str:
    cleaned = (
        name.lower()
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("à", "a")
        .replace("ç", "c")
        .replace("ô", "o")
        .replace("î", "i")
        .replace("û", "u")
        .replace("ù", "u")
        .replace("`", "")
        .replace("'", "")
        .strip()
    )
    return TEAM_ALIASES.get(cleaned, cleaned)


def display_team(name: str) -> str:
    aliases = {
        "MAROC": "Maroc",
        "NORVEGE": "Norvege",
        "ARGENTINE": "Argentine",
        "BELGIQUE": "Belgique",
        "SUISSE": "Suisse",
    }
    if name in aliases:
        return aliases[name]
    if name.isupper():
        return name.title()
    return name


def teams_match(name_a: str, name_b: str) -> bool:
    a = normalize_team(name_a)
    b = normalize_team(name_b)
    return a == b or a in b or b in a


def match_coteur_to_pinnacle_event(
    coteur_data: dict[str, Any],
    pinnacle_events: list[dict],
) -> dict | None:
    info = coteur_data.get("info") or {}
    home = (info.get("teamDom") or {}).get("equipeNom", "")
    away = (info.get("teamExt") or {}).get("equipeNom", "")

    for event in pinnacle_events:
        if teams_match(home, event["home_team"]) and teams_match(away, event["away_team"]):
            return event
        if teams_match(home, event["away_team"]) and teams_match(away, event["home_team"]):
            return event
    return None


def build_bookmaker_catalog(coteur: CoteurClient) -> dict[int, str]:
    return {
        int(book["id"]): normalize_bookmaker_name(book.get("nom", str(book["id"])))
        for book in coteur.get_bookmakers()
        if "id" in book
    }


def normalize_coteur_price_map(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {str(key): odds for key, odds in value.items()}
    if isinstance(value, list):
        return {str(index): odds for index, odds in enumerate(value)}
    return {}


def normalize_point_str(value: str) -> str:
    if not value:
        return ""
    try:
        number = float(value)
    except ValueError:
        return value
    if number.is_integer():
        return str(int(number))
    return str(number)


def build_pinnacle_variant_map(pinnacle_event: dict[str, Any]) -> dict[str, dict[str, Any]]:
    variant_map: dict[str, dict[str, Any]] = {}
    for market in pinnacle_event.get("markets", []):
        market_key = map_pinnacle_guest_market_to_compare_key(market)
        if not market_key:
            continue
        point = extract_pinnacle_guest_point(market)
        entries = build_pinnacle_outcome_entries(market_key, market, pinnacle_event)
        if market_key == "player_goal_scorer_anytime":
            existing = variant_map.setdefault(
                market_key,
                {
                    "market_key": market_key,
                    "point": point,
                    "outcomes": [],
                    "market_label": market.get("market_group_label", ""),
                    "variant_label": market.get("variant_label", ""),
                },
            )
            existing["outcomes"].extend(entries)
            continue
        variant_map[market_key] = {
            "market_key": market_key.split("|", 1)[0],
            "point": point,
            "outcomes": entries,
            "market_label": market.get("market_group_label", ""),
            "variant_label": market.get("variant_label", ""),
        }
    return variant_map


def extract_pinnacle_guest_point(market: dict[str, Any]) -> str:
    for outcome in market.get("prices", []):
        points = outcome.get("points")
        if points is not None:
            return normalize_point_str(str(points))
    return ""


def normalize_pinnacle_guest_outcome(
    compare_key: str,
    raw_label: str,
    home_team: str,
    away_team: str,
) -> str:
    label = raw_label.strip()
    lower = label.lower()
    if compare_key in {"btts", "btts_h1"}:
        if lower == "yes":
            return "Oui"
        if lower == "no":
            return "Non"
    if compare_key in {"double_chance", "double_chance_h1"}:
        cleaned = label.replace(" Or ", " or ")
        if cleaned == f"{home_team} or Draw":
            return f"{home_team} ou Nul"
        if cleaned == f"Draw or {away_team}":
            return f"{away_team} ou Nul"
        if cleaned == f"{home_team} or {away_team}":
            return f"{home_team} ou {away_team}"
    if compare_key == "halftime_fulltime":
        parts = [part.strip() for part in label.replace(" - ", "/").split("/")]
        normalized = []
        for part in parts:
            if part.lower() == "draw":
                normalized.append("Nul")
            else:
                normalized.append(part)
        return "/".join(normalized)
    return label


def build_pinnacle_outcome_entries(
    compare_key: str,
    market: dict[str, Any],
    pinnacle_event: dict[str, Any],
) -> list[dict[str, Any]]:
    entries = []
    home_team = str(pinnacle_event.get("home_team", ""))
    away_team = str(pinnacle_event.get("away_team", ""))
    description = str(market.get("description") or "")
    variant_label = str(market.get("variant_label") or "")

    if compare_key == "player_goal_scorer_anytime":
        yes_price = next(
            (outcome for outcome in market.get("prices", []) if str(outcome.get("outcome", "")).lower() == "yes"),
            None,
        )
        player_name = description.replace(" To Score", "").strip() or variant_label.replace(" To Score", "").strip()
        if yes_price and yes_price.get("decimal_odds") is not None and player_name:
            entries.append(
                {
                    "label": player_name,
                    "raw_name": player_name,
                    "description": description,
                    "odds": float(yes_price.get("decimal_odds")),
                }
            )
        return entries

    for outcome in market.get("prices", []):
        if outcome.get("decimal_odds") is None:
            continue
        raw_label = str(outcome.get("outcome", ""))
        entries.append(
            {
                "label": normalize_pinnacle_guest_outcome(compare_key, raw_label, home_team, away_team),
                "raw_name": str(outcome.get("designation", "") or outcome.get("participant_id", "")),
                "description": description,
                "odds": float(outcome.get("decimal_odds")),
            }
        )
    return entries


def map_pinnacle_guest_market_to_compare_key(market: dict[str, Any]) -> str | None:
    market_type = str(market.get("market_type", ""))
    period = int(market.get("period", 0))
    label = str(market.get("market_group_label", ""))
    description = str(market.get("description", ""))
    line = extract_pinnacle_guest_point(market)

    if label == "1X2":
        if period == 0:
            return "h2h"
        if period == 1:
            return "h2h_h1"
        if period == 8:
            return "to_qualify"
    if label == "Over/Under" and line:
        if period == 0:
            return f"totals|{line}"
        if period == 1:
            return f"totals_h1|{line}"
    if label in {"Double Chance", "Double Chance 1st Half"}:
        if period == 0 and label == "Double Chance":
            return "double_chance"
        if period == 1 or label == "Double Chance 1st Half":
            return "double_chance_h1"
    if label in {"Draw No Bet", "Draw No Bet 1st Half"}:
        if period == 0:
            return "draw_no_bet"
    if label in {"Both Teams To Score?", "Both Teams To Score? 1st Half"}:
        if period == 0:
            return "btts"
    if label == "Half-Time/Full-Time":
        return "halftime_fulltime"
    if label == "Anytime Goalscorer":
        return "player_goal_scorer_anytime"
    if description == "Anytime Goalscorer":
        return "player_goal_scorer_anytime"
    if description.endswith(" To Score"):
        return "player_goal_scorer_anytime"
    if label == "Vainqueur" and period == 8 and market_type == "moneyline":
        return "to_qualify"
    return None


def build_coteur_variant_rows(
    coteur: CoteurClient,
    match: dict[str, Any],
    coteur_data: dict[str, Any],
    bookmaker_names: dict[int, str],
) -> list[dict[str, Any]]:
    info = coteur_data.get("info") or {}
    home_team = display_team((info.get("teamDom") or {}).get("equipeNom", ""))
    away_team = display_team((info.get("teamExt") or {}).get("equipeNom", ""))
    event = f"{home_team} vs {away_team}"
    player_names = build_player_name_map(coteur, coteur_data)

    variants = []
    for entry in coteur_data.get("odds", []):
        typename = entry.get("typename", "")
        special = entry.get("special") or ""
        pinnacle_key = map_coteur_to_pinnacle(typename, special)
        market_data = coteur.get_market_odds(match["renc_id"], typename, special)
        bookmakers = []
        outcome_map: dict[str, list[dict[str, Any]]] = {}
        for value in market_data.get("values", []):
            bookmaker_id = value.get("bookId")
            bookmaker_name = build_bookmaker_name(bookmaker_id, bookmaker_names)
            current = normalize_coteur_price_map(value.get("current"))
            previous = normalize_coteur_price_map(value.get("previous"))
            bookmakers.append(
                {
                    "bookmaker_id": bookmaker_id,
                    "bookmaker": bookmaker_name,
                    "disabled": bool(value.get("disable", False)),
                    "last_update": value.get("lastUpdate", ""),
                }
            )
            for raw_outcome, odds in current.items():
                label = coteur_outcome_label(typename, str(raw_outcome), home_team, away_team)
                if typename == "BUTEUR":
                    label = player_names.get(str(raw_outcome), label)
                elif label == "draw":
                    label = "Nul"
                elif label == "yes":
                    label = "Oui"
                elif label == "no":
                    label = "Non"
                outcome_map.setdefault(label, []).append(
                    {
                        "raw_outcome": str(raw_outcome),
                        "bookmaker_id": bookmaker_id,
                        "bookmaker": bookmaker_name,
                        "odds": odds,
                        "previous_odds": previous.get(raw_outcome, ""),
                        "disabled": bool(value.get("disable", False)),
                        "last_update": value.get("lastUpdate", ""),
                    }
                )
        for values in outcome_map.values():
            values.sort(key=lambda item: str(item["bookmaker"]))
        bookmakers.sort(key=lambda item: str(item["bookmaker"]))
        variants.append(
            {
                "market_type": typename,
                "market_special": special,
                "market_label": entry.get("typename"),
                "pinnacle_key": pinnacle_key,
                "outcomes": outcome_map,
                "bookmakers": bookmakers,
            }
        )
    return variants


def compare_match(
    coteur: CoteurClient,
    coteur_match: dict[str, Any],
    pinnacle_event: dict,
    bookmaker_names: dict[int, str],
    coteur_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    coteur_data = coteur_data or coteur.get_full_odds(coteur_match["renc_id"])
    info = coteur_data.get("info") or {}
    home_team = display_team((info.get("teamDom") or {}).get("equipeNom", ""))
    away_team = display_team((info.get("teamExt") or {}).get("equipeNom", ""))

    pinnacle_variants = build_pinnacle_variant_map(pinnacle_event)
    coteur_variants = build_coteur_variant_rows(coteur, coteur_match, coteur_data, bookmaker_names)

    comparable_markets = []
    coteur_only = []
    for variant in coteur_variants:
        pk = variant["pinnacle_key"]
        if not pk or pk not in pinnacle_variants:
            coteur_only.append(
                {
                    "market_type": variant["market_type"],
                    "market_special": variant["market_special"],
                    "pinnacle_key": pk,
                }
            )
            continue

        pinn = pinnacle_variants[pk]
        outcome_labels = sorted(set(variant["outcomes"]).intersection({o["label"] for o in pinn["outcomes"]}))
        outcome_comparisons = []
        for label in outcome_labels:
            pinnacle_outcome = next(o for o in pinn["outcomes"] if o["label"] == label)
            coteur_prices = sorted(
                variant["outcomes"][label],
                key=lambda item: item["odds"],
                reverse=True,
            )
            outcome_comparisons.append(
                {
                    "outcome": label,
                    "pinnacle_odds": pinnacle_outcome["odds"],
                    "coteur_prices": coteur_prices,
                    "best_coteur_price": coteur_prices[0]["odds"] if coteur_prices else None,
                    "best_coteur_bookmaker": coteur_prices[0]["bookmaker"] if coteur_prices else None,
                    "price_delta": (coteur_prices[0]["odds"] - pinnacle_outcome["odds"]) if coteur_prices else None,
                }
            )

        if not outcome_comparisons:
            coteur_only.append(
                {
                    "market_type": variant["market_type"],
                    "market_special": variant["market_special"],
                    "pinnacle_key": pk,
                    "reason": "no_common_outcomes",
                }
            )
            continue

        comparable_markets.append(
            {
                "pinnacle_key": pk,
                "coteur_market_type": variant["market_type"],
                "coteur_market_special": variant["market_special"],
                "coteur_market_label": coteur_market_label(
                    variant["market_type"],
                    variant["market_special"],
                ),
                "line": pinn["point"] or "",
                "outcomes_compared": outcome_comparisons,
                "coteur_bookmakers": variant["bookmakers"],
                "matched_outcomes_count": len(outcome_comparisons),
                "coteur_outcomes_count": len(variant["outcomes"]),
                "pinnacle_outcomes_count": len(pinn["outcomes"]),
            }
        )

    pinnacle_only = sorted(set(pinnacle_variants) - {m["pinnacle_key"] for m in comparable_markets if m["pinnacle_key"]})

    return {
        "event": f"{pinnacle_event['home_team']} vs {pinnacle_event['away_team']}",
        "event_display_fr": f"{home_team} vs {away_team}",
        "commence_time": pinnacle_event.get("commence_time", ""),
        "coteur_renc_id": coteur_match["renc_id"],
        "coteur_url": coteur_match["url"],
        "pinnacle_event_id": pinnacle_event["matchup_id"],
        "comparable_market_count": len(comparable_markets),
        "comparable_markets": comparable_markets,
        "coteur_only_markets": coteur_only,
        "pinnacle_only_markets": pinnacle_only,
        "pinnacle_market_count": len(pinnacle_event.get("markets", [])),
        "coteur_market_count": len(coteur_variants),
    }


def write_csv_rows(results: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "event",
                "event_display_fr",
                "pinnacle_key",
                "coteur_market_type",
                "coteur_market_special",
                "line",
                "outcome",
                "pinnacle_odds",
                "best_coteur_odds",
                "best_coteur_bookmaker",
                "price_delta",
            ],
        )
        writer.writeheader()

        for result in results:
            for market in result["comparable_markets"]:
                for outcome in market["outcomes_compared"]:
                    writer.writerow({
                        "event": result["event"],
                        "event_display_fr": result["event_display_fr"],
                        "pinnacle_key": market["pinnacle_key"],
                        "coteur_market_type": market["coteur_market_type"],
                        "coteur_market_special": market["coteur_market_special"],
                        "line": market["line"],
                        "outcome": outcome["outcome"],
                        "pinnacle_odds": outcome["pinnacle_odds"],
                        "best_coteur_odds": outcome["best_coteur_price"],
                        "best_coteur_bookmaker": outcome["best_coteur_bookmaker"],
                        "price_delta": outcome["price_delta"],
                    })


def print_summary(results: list[dict[str, Any]]) -> None:
    for result in results:
        log.info("")
        log.info("=== %s ===", result["event_display_fr"])
        log.info(
            "Coteur: %d marchés | Pinnacle: %d | Comparables: %d",
            result["coteur_market_count"],
            result["pinnacle_market_count"],
            result["comparable_market_count"],
        )
        for market in result["comparable_markets"][:6]:
            log.info(
                "  ✓ %s (%s)",
                market["pinnacle_key"],
                market["coteur_market_type"] + (f" {market['coteur_market_special']}" if market["coteur_market_special"] else ""),
            )
        if len(result["comparable_markets"]) > 6:
            log.info("  ... +%d marchés comparables", len(result["comparable_markets"]) - 6)
        if result["coteur_only_markets"]:
            log.info("  Coteur seulement: %d", len(result["coteur_only_markets"]))
        if result["pinnacle_only_markets"]:
            log.info("  Pinnacle seulement: %d", len(result["pinnacle_only_markets"]))


def run(output: Path | None = None) -> Path:
    coteur = CoteurClient()
    pinnacle = PinnacleGuestClient()
    bookmaker_names = build_bookmaker_catalog(coteur)

    log.info("Récupération matchs foot sur Coteur...")
    coteur_matches = coteur.list_football_matches()
    log.info("%d match(s) trouvé(s) sur Coteur", len(coteur_matches))

    leagues = pinnacle.list_active_soccer_leagues()
    log.info("%d ligue(s) foot active(s) sur Pinnacle", len(leagues))
    pinnacle_events = []
    seen_matchups: set[int] = set()
    for league in leagues:
        pinnacle_matchups = pinnacle.get_league_matchups(league.id)
        main_matchups = [matchup for matchup in pinnacle_matchups if is_main_event(matchup)]
        log.info("Pinnacle %s | %s : %d match(s)", league.group, league.name, len(main_matchups))
        for matchup in main_matchups:
            matchup_id = int(matchup["id"])
            if matchup_id in seen_matchups:
                continue
            seen_matchups.add(matchup_id)
            pinnacle_events.append(build_event_payload(pinnacle, matchup))
    log.info("%d match(s) trouvé(s) sur Pinnacle", len(pinnacle_events))

    results = []
    for coteur_match in coteur_matches:
        coteur_data = coteur.get_full_odds(coteur_match["renc_id"])
        pinnacle_event = match_coteur_to_pinnacle_event(coteur_data, pinnacle_events)
        if not pinnacle_event:
            info = coteur_data.get("info") or {}
            log.warning(
                "Pas de correspondance Pinnacle pour %s vs %s",
                (info.get("teamDom") or {}).get("equipeNom", coteur_match["slug"]),
                (info.get("teamExt") or {}).get("equipeNom", "?"),
            )
            continue

        log.info("Comparaison: %s vs %s", pinnacle_event["home_team"], pinnacle_event["away_team"])
        results.append(
            compare_match(
                coteur,
                coteur_match,
                pinnacle_event,
                bookmaker_names,
                coteur_data,
            )
        )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output or OUTPUT_DIR / f"market_compare_{stamp}.json"
    csv_path = json_path.with_suffix(".csv")

    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "source": "coteur_vs_pinnacle",
                "sport": "soccer_all",
                "generated_at": datetime.now().isoformat(),
                "partial": False,
                "league_count": len(leagues),
                "results": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    write_csv_rows(results, csv_path)
    print_summary(results)

    log.info("Export JSON : %s", json_path.resolve())
    log.info("Export CSV  : %s", csv_path.resolve())
    return json_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compare marchés Coteur vs Pinnacle (football global)"
    )
    parser.add_argument("-o", "--output", type=Path, help="Fichier JSON de sortie")
    args = parser.parse_args()
    run(args.output)
