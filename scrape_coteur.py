"""Exporte les cotes Coteur (books FR) pour le foot CDM."""

import argparse
import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from coteur_client import CoteurClient
from market_mapping import (
    coteur_market_group_display_label,
    coteur_market_group_key,
    coteur_market_group_label,
    coteur_market_label,
    coteur_market_variant_label,
    coteur_outcome_label,
    coteur_special_line,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("scrape_coteur")

OUTPUT_DIR = Path(__file__).parent / "output"


def build_bookmaker_name(bookmaker_id: int | None, bookmaker_names: dict[int, str]) -> str | int | None:
    if bookmaker_id is None:
        return None
    return bookmaker_names.get(bookmaker_id, bookmaker_id)


def normalize_bookmaker_name(name: str) -> str:
    normalized = {
        "PMU": "PMU",
        "Winamax": "Winamax",
        "Unibet": "Unibet",
        "Betclic": "Betclic",
        "Netbet": "NetBet",
        "Bet365": "Bet365",
        "Bwin": "Bwin",
        "Zebet": "ZEbet",
        "Parions sport": "Parions Sport",
        "Vbet": "VBet",
        "Feelingbet": "FeelingBet",
        "Betsson": "Betsson",
        "Olybet": "OlyBet",
        "DaznBet": "DAZN Bet",
        "Genybet": "Genybet",
    }
    return normalized.get(name, name)


def normalize_team_display(name: str) -> str:
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


def build_player_name_map(client: CoteurClient, data: dict[str, Any]) -> dict[str, str]:
    player_ids: set[str] = set()
    for entry in data.get("odds", []):
        if entry.get("typename") != "BUTEUR":
            continue
        player_ids.update((entry.get("bestfr") or entry.get("best") or {}).keys())

    if not player_ids:
        return {}

    players = client.get_players(sorted(player_ids))
    return {
        str(player["playerId"]): player.get("nom", str(player["playerId"]))
        for player in players
    }


def build_market_rows(
    client: CoteurClient,
    match: dict,
    entry: dict,
    event: str,
    bookmaker_names: dict[int, str],
) -> list[dict]:
    typename = entry.get("typename", "")
    special = entry.get("special") or ""
    label = coteur_market_label(typename, special)
    market_data = client.get_market_odds(match["renc_id"], typename, special)

    rows = []
    for value in market_data.get("values", []):
        bookmaker_id = value.get("bookId")
        current = value.get("current") or {}
        previous = value.get("previous") or {}
        if isinstance(current, list):
            current = {str(index): odds for index, odds in enumerate(current)}
        if isinstance(previous, list):
            previous = {str(index): odds for index, odds in enumerate(previous)}

        for outcome, odds in current.items():
            rows.append({
                "event": event,
                "renc_id": match["renc_id"],
                "market_type": typename,
                "market_special": special,
                "market_label": label,
                "outcome": outcome,
                "bookmaker_id": bookmaker_id,
                "bookmaker": build_bookmaker_name(bookmaker_id, bookmaker_names),
                "odds": odds,
                "previous_odds": previous.get(outcome, ""),
                "disabled": value.get("disable", False),
                "last_update": value.get("lastUpdate", ""),
            })
    return rows


def build_market_payload(entry: dict, rows: list[dict]) -> dict:
    typename = entry.get("typename", "")
    special = entry.get("special") or ""
    label = coteur_market_label(typename, special)

    bookmakers: dict[str, dict] = {}
    outcomes: dict[str, list[dict]] = {}

    for row in rows:
        bookmaker_key = str(row["bookmaker"])
        bookmakers[bookmaker_key] = {
            "bookmaker_id": row["bookmaker_id"],
            "bookmaker": row["bookmaker"],
            "disabled": row["disabled"],
            "last_update": row["last_update"],
        }
        outcomes.setdefault(str(row["outcome"]), []).append(
            {
                "bookmaker_id": row["bookmaker_id"],
                "bookmaker": row["bookmaker"],
                "odds": row["odds"],
                "previous_odds": row["previous_odds"],
                "disabled": row["disabled"],
                "last_update": row["last_update"],
            }
        )

    for values in outcomes.values():
        values.sort(key=lambda item: str(item["bookmaker"]))

    return {
        "market_type": typename,
        "market_special": special,
        "market_label": label,
        "bookmakers": sorted(bookmakers.values(), key=lambda item: str(item["bookmaker"])),
        "outcomes": outcomes,
    }


def build_event_payload(
    match: dict,
    data: dict,
    market_rows: dict[tuple[str, str], list[dict]],
    player_names: dict[str, str],
) -> dict:
    info = data.get("info") or {}
    home = normalize_team_display((info.get("teamDom") or {}).get("equipeNom", ""))
    away = normalize_team_display((info.get("teamExt") or {}).get("equipeNom", ""))

    market_groups: dict[str, dict] = {}
    for entry in data.get("odds", []):
        typename = entry.get("typename", "")
        special = entry.get("special") or ""
        key = (typename, special)
        rows = market_rows.get(key, [])

        group_key = coteur_market_group_key(typename, special)
        group = market_groups.setdefault(
            group_key,
            {
                "market_group_key": group_key,
                "market_group_label": coteur_market_group_display_label(typename, special),
                "variants": [],
            },
        )

        variant_outcomes: dict[str, list[dict]] = {}
        bookmakers: dict[str, dict] = {}
        for row in rows:
            normalized_outcome = coteur_outcome_label(
                typename,
                str(row["outcome"]),
                home,
                away,
            )
            if typename == "BUTEUR":
                normalized_outcome = player_names.get(str(row["outcome"]), normalized_outcome)
            bookmakers[str(row["bookmaker"])] = {
                "bookmaker_id": row["bookmaker_id"],
                "bookmaker": row["bookmaker"],
                "disabled": row["disabled"],
                "last_update": row["last_update"],
            }
            variant_outcomes.setdefault(normalized_outcome, []).append(
                {
                    "raw_outcome": row["outcome"],
                    "bookmaker_id": row["bookmaker_id"],
                    "bookmaker": row["bookmaker"],
                    "odds": row["odds"],
                    "previous_odds": row["previous_odds"],
                    "disabled": row["disabled"],
                    "last_update": row["last_update"],
                }
            )

        for values in variant_outcomes.values():
            values.sort(key=lambda item: str(item["bookmaker"]))

        group["variants"].append(
            {
                "market_key": f"{typename}|{special}" if special else typename,
                "market_type": typename,
                "market_special": special,
                "market_label": coteur_market_label(typename, special),
                "variant_label": coteur_market_variant_label(typename, special),
                "line": coteur_special_line(typename, special),
                "bookmakers": sorted(
                    bookmakers.values(),
                    key=lambda item: str(item["bookmaker"]),
                ),
                "outcomes": variant_outcomes,
            }
        )

    markets = sorted(
        market_groups.values(),
        key=lambda item: item["market_group_label"],
    )
    for group in markets:
        group["variants"].sort(
            key=lambda item: (
                item["line"] is not None and item["line"] != "",
                str(item["line"]),
                item["market_label"],
            )
        )

    return {
        "event": f"{home} vs {away}",
        "renc_id": match["renc_id"],
        "slug": match["slug"],
        "url": match["url"],
        "start_time": info.get("rencDate", ""),
        "sport": (info.get("sport") or {}).get("sportNom", ""),
        "competition_id": info.get("competId"),
        "market_group_count": len(markets),
        "home_team": {
            "id": (info.get("teamDom") or {}).get("equipeId"),
            "name": home,
            "logo": (info.get("teamDom") or {}).get("logo"),
        },
        "away_team": {
            "id": (info.get("teamExt") or {}).get("equipeId"),
            "name": away,
            "logo": (info.get("teamExt") or {}).get("logo"),
        },
        "market_groups": markets,
    }


def export_football(output: Path | None = None, csv_output: Path | None = None) -> Path:
    client = CoteurClient()
    bookmaker_catalog = client.get_bookmakers()
    bookmaker_names = {
        int(book["id"]): normalize_bookmaker_name(book.get("nom", str(book["id"])))
        for book in bookmaker_catalog
        if "id" in book
    }
    matches = client.list_football_matches()
    log.info("%d match(s) foot sur Coteur", len(matches))

    rows = []
    events = []
    for match in matches:
        data = client.get_full_odds(match["renc_id"])
        info = data.get("info") or {}
        home = normalize_team_display((info.get("teamDom") or {}).get("equipeNom", ""))
        away = normalize_team_display((info.get("teamExt") or {}).get("equipeNom", ""))
        event = f"{home} vs {away}"
        match_rows_before = len(rows)
        market_rows: dict[tuple[str, str], list[dict]] = {}
        player_names = build_player_name_map(client, data)

        for entry in data.get("odds", []):
            entry_rows = build_market_rows(client, match, entry, event, bookmaker_names)
            rows.extend(entry_rows)
            market_rows[(entry.get("typename", ""), entry.get("special") or "")] = entry_rows

        events.append(build_event_payload(match, data, market_rows, player_names))

        log.info("%s : %d ligne(s)", event, len(rows) - match_rows_before)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output or OUTPUT_DIR / f"coteur_football_{stamp}.json"
    csv_path = csv_output or json_path.with_suffix(".csv")
    json_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "source": "coteur",
        "competition": "All football competitions",
        "sport": "Football",
        "generated_at": datetime.now().isoformat(),
        "event_count": len(events),
        "events": events,
    }

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "event", "renc_id", "market_type", "market_special",
                "market_label", "outcome", "bookmaker_id", "bookmaker", "odds",
                "previous_odds", "disabled", "last_update",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    log.info("%d événement(s) exporté(s) → %s", len(events), json_path.resolve())
    log.info("%d lignes CSV exportées → %s", len(rows), csv_path.resolve())
    return json_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export cotes Coteur football")
    parser.add_argument("-o", "--output", type=Path, help="Fichier JSON de sortie")
    parser.add_argument("--csv-output", type=Path, help="Fichier CSV de sortie")
    args = parser.parse_args()
    export_football(args.output, args.csv_output)
