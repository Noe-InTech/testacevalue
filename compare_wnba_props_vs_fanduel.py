"""Compare stats joueuses WNBA — books FR vs FanDuel.

Pipeline séparé du tennis : ne modifie pas compare_tennis_*.
"""

from __future__ import annotations

import argparse
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

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


def props_outcome_label_fr(outcome: str) -> str:
    if outcome == "Over":
        return "Plus"
    if outcome == "Under":
        return "Moins"
    if outcome == "Yes":
        return "Oui"
    return outcome


def enrich_comparable_row(row: dict[str, Any]) -> dict[str, Any]:
    fr_odds = round(float(row["best_fr_odds"]), 2)
    fd_decimal = round(float(row["fanduel_odds"]), 2)
    price_delta = round(fr_odds - fd_decimal, 2)
    if price_delta > 0:
        best_side = "fr"
    elif price_delta < 0:
        best_side = "fanduel"
    else:
        best_side = "tie"
    issue = props_outcome_label_fr(str(row.get("outcome", "")))
    marche_fr = str(row.get("fr_market_label", ""))
    marche_fd = str(row.get("fanduel_market_label", ""))
    enriched = {
        **row,
        "best_side": best_side,
        "cote_fr": format_french_decimal(fr_odds),
        "bookmaker_fr": row.get("best_fr_bookmaker", ""),
        "cote_us_fanduel_ml": format_american_moneyline(row.get("fanduel_american")),
        "cote_fr_fanduel": format_french_decimal(fd_decimal),
        "ecart_fr_moins_fd": f"{price_delta:+.2f}".replace(".", ","),
        "meilleur_cote": "FR" if best_side == "fr" else "FanDuel" if best_side == "fanduel" else "Egalite",
        "issue_fr": issue,
        "marche_fr": marche_fr,
        "marche_fanduel": marche_fd,
        "ligne_props_fr": format_ligne_props_fr(row),
    }
    return enriched


def enrich_fr_only_row(row: dict[str, Any]) -> dict[str, Any]:
    issue = props_outcome_label_fr(str(row.get("outcome", "")))
    marche_fr = str(row.get("fr_market_label", ""))
    return {
        **row,
        "cote_fr": format_french_decimal(float(row["best_fr_odds"])),
        "bookmaker_fr": row.get("best_fr_bookmaker", ""),
        "cote_us_fanduel_ml": "",
        "cote_fr_fanduel": "",
        "ecart_fr_moins_fd": "",
        "meilleur_cote": "FR seul",
        "issue_fr": issue,
        "marche_fr": marche_fr,
        "marche_fanduel": "",
        "ligne_props_fr": format_ligne_props_fr(row),
    }


def enrich_fd_only_row(row: dict[str, Any]) -> dict[str, Any]:
    issue = props_outcome_label_fr(str(row.get("outcome", "")))
    marche_fd = str(row.get("fanduel_market_label", ""))
    return {
        **row,
        "cote_fr": "",
        "bookmaker_fr": "",
        "cote_us_fanduel_ml": row.get("cote_us_fanduel_ml", ""),
        "cote_fr_fanduel": row.get("cote_fr_fanduel", ""),
        "ecart_fr_moins_fd": "",
        "meilleur_cote": "FanDuel seul",
        "issue_fr": issue,
        "marche_fr": "",
        "marche_fanduel": marche_fd,
        "ligne_props_fr": format_ligne_props_fr(row),
    }


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
            row = enrich_comparable_row(
                {
                    "compare_key": compare_key,
                    "market_family": fr_market["market_family"],
                    "player_name": fr_market.get("player_name", ""),
                    "outcome": outcome,
                    "fr_market_label": fr_market["market_label_raw"],
                    "fanduel_market_label": fd_market.get("market_label", ""),
                    "best_fr_odds": fr_payload["odds"],
                    "best_fr_bookmaker": fr_payload["bookmaker_label"],
                    "fanduel_american": fd_bundle.get("american"),
                    "fanduel_odds": float(fd_bundle.get("decimal_raw") or fd_bundle["decimal_fr"]),
                }
            )
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


def collect_comparable_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        for row in result.get("comparables", []):
            rows.append({"match": result["match"], **row})
    return rows


def collect_fr_higher_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("best_side") == "fr"]


def collect_fr_only_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        for row in result.get("fr_only", []):
            rows.append({"match": result["match"], **row})
    return rows


def collect_fd_only_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        for row in result.get("fd_only", []):
            rows.append({"match": result["match"], **row})
    return rows


def build_match_progress(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        rows.append(
            {
                "match": result.get("match", ""),
                "comparable_count": int(result.get("comparable_count", 0)),
                "fr_only_count": int(result.get("fr_only_count", 0)),
                "fd_only_count": int(result.get("fd_only_count", 0)),
                "fr_market_count": int(result.get("fr_prop_market_count", 0)),
                "fd_market_count": int(result.get("fd_prop_market_count", 0)),
                "fanduel_found": bool(result.get("fanduel_event_id")),
            }
        )
    return rows


def build_results_payload(
    results: list[dict[str, Any]],
    *,
    partial: bool,
    anchors_total: int | None = None,
    book_warnings: list[str] | None = None,
) -> dict[str, Any]:
    comparable_rows = collect_comparable_rows(results)
    fr_higher_rows = collect_fr_higher_rows(comparable_rows)
    fr_only_rows = collect_fr_only_rows(results)
    fd_only_rows = collect_fd_only_rows(results)
    match_progress = build_match_progress(results)
    fd_events = sum(1 for result in results if int(result.get("fd_prop_market_count", 0)) > 0)
    fr_events = sum(1 for result in results if int(result.get("fr_prop_market_count", 0)) > 0)
    return {
        "source": "wnba_player_props_comparable",
        "generated_at": utc_now(),
        "partial": partial,
        "anchors_total": anchors_total if anchors_total is not None else len(match_progress),
        "matches_done": len(match_progress),
        "comparable_count": len(comparable_rows),
        "fr_higher_count": len(fr_higher_rows),
        "value_count": 0,
        "fr_only_count": len(fr_only_rows),
        "fd_only_count": len(fd_only_rows),
        "fd_event_count": fd_events,
        "fr_event_count": fr_events,
        "comparables": comparable_rows,
        "fr_higher_comparables": fr_higher_rows,
        "value_comparables": [],
        "fr_only_comparables": fr_only_rows,
        "fd_only_comparables": fd_only_rows,
        "match_progress": match_progress,
        "notes": [
            "Pipeline WNBA séparé du tennis.",
            "Référence US: FanDuel (props joueuse O/U).",
            "Books FR: Unibet, Betclic, Winamax — meilleure cote par compare_key.",
            *(book_warnings or []),
        ],
    }


def write_progress_json(
    path: Path | None,
    results: list[dict[str, Any]],
    *,
    partial: bool,
    anchors_total: int | None = None,
) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_results_payload(results, partial=partial, anchors_total=anchors_total)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def write_run_status_file(
    path: Path | None,
    status: str,
    message: str,
    *,
    match_filter: str = "",
    results: list[dict[str, Any]] | None = None,
    anchors_total: int | None = None,
) -> None:
    if path is None:
        return
    payload: dict[str, Any] = {
        "status": status,
        "message": message,
        "match_filter": match_filter,
        "sport": "wnba",
        "updated_at": utc_now(),
    }
    if anchors_total is not None:
        payload["anchors_total"] = anchors_total
    if results is not None:
        comparable_rows = collect_comparable_rows(results)
        payload["comparable_count"] = len(comparable_rows)
        payload["fr_higher_count"] = len(collect_fr_higher_rows(comparable_rows))
        payload["value_count"] = 0
        payload["matches_done"] = len(results)
        payload["fr_only_count"] = sum(int(item.get("fr_only_count", 0)) for item in results)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_call(label: str, callback: Callable[[], Any], fallback: Any) -> Any:
    try:
        return callback()
    except Exception as exc:
        log.warning("%s indisponible (live): %s", label, exc)
        return fallback


def fetch_live_wnba_listings(
    *,
    unibet: UnibetBasketballClient,
    betclic: BetclicBasketballClient,
    winamax: WinamaxBasketballClient,
    fanduel: FanDuelBasketballClient,
    on_status: Callable[[str], None] | None = None,
) -> tuple[list[Any], list[Any], list[Any], list[Any], list[str]]:
    def status(message: str) -> None:
        if on_status is not None:
            on_status(message)

    warnings: list[str] = []
    status("Chargement parallele des calendriers WNBA...")

    with ThreadPoolExecutor(max_workers=4) as pool:
        fut_unibet = pool.submit(unibet.list_wnba_events)
        fut_betclic = pool.submit(betclic.list_wnba_matches)
        fut_winamax = pool.submit(winamax.list_wnba_matches)
        fut_fanduel = pool.submit(fanduel.list_wnba_events)

        unibet_events = _safe_call("Unibet", fut_unibet.result, [])
        betclic_links = _safe_call("Betclic", fut_betclic.result, [])
        winamax_links = _safe_call("Winamax", fut_winamax.result, [])
        fanduel_events = _safe_call("FanDuel", fut_fanduel.result, [])

    if not unibet_events:
        warnings.append("Unibet indisponible depuis le runner EU (souvent bloque IP datacenter).")
    if not betclic_links:
        warnings.append("Betclic: aucun match WNBA ou scrape indisponible.")
    if not winamax_links:
        warnings.append(
            "Winamax indisponible depuis le runner EU (IP Oracle bloquee — compare sans Winamax)."
        )
    if not fanduel_events:
        warnings.append("FanDuel: aucun evenement WNBA ou scrape indisponible.")

    status(
        "Calendriers WNBA — "
        f"Unibet {len(unibet_events)}, Betclic {len(betclic_links)}, "
        f"Winamax {len(winamax_links)}, FanDuel {len(fanduel_events)}"
    )
    return unibet_events, betclic_links, winamax_links, fanduel_events, warnings


def compare_anchor(
    anchor: dict[str, Any],
    *,
    unibet_events: list[Any],
    betclic_links: list[Any],
    winamax_links: list[Any],
    fanduel_events: list[Any],
    unibet: UnibetBasketballClient,
    betclic: BetclicBasketballClient,
    winamax: WinamaxBasketballClient,
    fanduel: FanDuelBasketballClient,
) -> dict[str, Any]:
    book_events: dict[str, dict[str, Any]] = {}

    unibet_event = next(
        (item for item in unibet_events if item.event_id == anchor.get("unibet_event_id")),
        None,
    )
    if unibet_event:
        payload = _safe_call(
            "Unibet",
            lambda: unibet.build_event_payload(unibet_event),
            None,
        )
        if payload:
            book_events["unibet"] = payload

    betclic_link = next(
        (item for item in betclic_links if item.match_id == anchor.get("betclic_match_id")),
        None,
    )
    if betclic_link:
        payload = _safe_call(
            "Betclic",
            lambda: betclic.build_event_payload(betclic_link),
            None,
        )
        if payload:
            book_events["betclic"] = payload

    winamax_link = next(
        (item for item in winamax_links if item.match_id == anchor.get("winamax_match_id")),
        None,
    )
    if winamax_link:
        payload = _safe_call(
            "Winamax",
            lambda: winamax.build_event_payload(winamax_link),
            None,
        )
        if payload:
            book_events["winamax"] = payload

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
            fanduel_payload = _safe_call(
                "FanDuel",
                lambda: fanduel.build_event_payload(event),
                None,
            )

    fr_map = build_best_fr_player_props_map(book_events, roster=roster)
    fd_map = build_fanduel_player_props_map(fanduel_payload, roster=roster)
    comparable = compare_normalized_props(fr_map, fd_map)

    fr_only: list[dict[str, Any]] = []
    for compare_key, fr_market in fr_map.items():
        fd_market = fd_map.get(compare_key)
        for outcome, fr_payload in fr_market["outcomes"].items():
            if fd_market and outcome in fd_market.get("outcomes", {}):
                continue
            fr_only.append(
                enrich_fr_only_row(
                    {
                        "compare_key": compare_key,
                        "market_family": fr_market["market_family"],
                        "player_name": fr_market.get("player_name", ""),
                        "outcome": outcome,
                        "best_fr_odds": fr_payload["odds"],
                        "best_fr_bookmaker": fr_payload["bookmaker_label"],
                        "fr_market_label": fr_market["market_label_raw"],
                    }
                )
            )

    fd_only: list[dict[str, Any]] = []
    for compare_key, fd_market in fd_map.items():
        fr_market = fr_map.get(compare_key)
        for outcome, fd_bundle in fd_market.get("outcomes", {}).items():
            if fr_market and outcome in fr_market.get("outcomes", {}):
                continue
            fd_only.append(
                enrich_fd_only_row(
                    {
                        "compare_key": compare_key,
                        "market_family": fd_market.get("market_family", compare_key.split("|", 1)[0]),
                        "player_name": "",
                        "outcome": outcome,
                        "fanduel_market_label": fd_market.get("market_label", ""),
                        "cote_fr_fanduel": format_french_decimal(float(fd_bundle["decimal_fr"])),
                        "cote_us_fanduel_ml": format_american_moneyline(fd_bundle.get("american")),
                    }
                )
            )

    return {
        "match": anchor["match"],
        "sources": sorted(anchor["sources"]),
        "fanduel_event_id": anchor.get("fanduel_event_id"),
        "comparable_count": len(comparable),
        "fr_only_count": len(fr_only),
        "fd_only_count": len(fd_only),
        "fr_prop_market_count": len(fr_map),
        "fd_prop_market_count": len(fd_map),
        "comparables": comparable,
        "fr_only": fr_only,
        "fd_only": fd_only,
    }


def run_compare(*, match_filter: str = "") -> dict[str, Any]:
    unibet = UnibetBasketballClient()
    betclic = BetclicBasketballClient()
    winamax = WinamaxBasketballClient(fetch_timeout=25)
    fanduel = FanDuelBasketballClient()

    unibet_events, betclic_links, winamax_links, fanduel_events, book_warnings = (
        fetch_live_wnba_listings(
            unibet=unibet,
            betclic=betclic,
            winamax=winamax,
            fanduel=fanduel,
        )
    )
    anchors = discover_anchors(
        unibet_events=unibet_events,
        betclic_links=betclic_links,
        winamax_links=winamax_links,
        fanduel_events=fanduel_events,
    )
    if match_filter:
        needle = match_filter.strip().lower()
        anchors = [anchor for anchor in anchors if needle in anchor["match"].lower()]

    results = [
        compare_anchor(
            anchor,
            unibet_events=unibet_events,
            betclic_links=betclic_links,
            winamax_links=winamax_links,
            fanduel_events=fanduel_events,
            unibet=unibet,
            betclic=betclic,
            winamax=winamax,
            fanduel=fanduel,
        )
        for anchor in anchors
    ]
    return build_results_payload(
        results,
        partial=False,
        anchors_total=len(anchors),
        book_warnings=book_warnings,
    )


def run_live_compare(
    output: Path | None = None,
    *,
    match_filter: str = "",
    progress_json: Path | None = None,
    status_json: Path | None = None,
) -> Path:
    unibet = UnibetBasketballClient()
    betclic = BetclicBasketballClient()
    winamax = WinamaxBasketballClient(fetch_timeout=25)
    fanduel = FanDuelBasketballClient()
    anchors_total = 0
    results: list[dict[str, Any]] = []
    book_warnings: list[str] = []

    def on_progress(message: str) -> None:
        write_progress_json(
            progress_json,
            results,
            partial=True,
            anchors_total=anchors_total,
        )
        write_run_status_file(
            status_json,
            "running",
            message,
            match_filter=match_filter,
            results=results,
            anchors_total=anchors_total,
        )

    write_run_status_file(
        status_json,
        "running",
        "Chargement des matchs WNBA...",
        match_filter=match_filter,
    )
    write_progress_json(progress_json, [], partial=True)

    def on_listing_status(message: str) -> None:
        write_run_status_file(status_json, "running", message, match_filter=match_filter)

    unibet_events, betclic_links, winamax_links, fanduel_events, book_warnings = (
        fetch_live_wnba_listings(
            unibet=unibet,
            betclic=betclic,
            winamax=winamax,
            fanduel=fanduel,
            on_status=on_listing_status,
        )
    )
    anchors = discover_anchors(
        unibet_events=unibet_events,
        betclic_links=betclic_links,
        winamax_links=winamax_links,
        fanduel_events=fanduel_events,
    )
    if match_filter:
        needle = match_filter.strip().lower()
        anchors = [anchor for anchor in anchors if needle in anchor["match"].lower()]

    anchors_total = len(anchors)
    write_run_status_file(
        status_json,
        "running",
        f"{anchors_total} match(s) WNBA — resultats au fil de l'eau...",
        match_filter=match_filter,
        anchors_total=anchors_total,
    )
    write_progress_json(progress_json, [], partial=True, anchors_total=anchors_total)

    for index, anchor in enumerate(anchors, start=1):
        compared = compare_anchor(
            anchor,
            unibet_events=unibet_events,
            betclic_links=betclic_links,
            winamax_links=winamax_links,
            fanduel_events=fanduel_events,
            unibet=unibet,
            betclic=betclic,
            winamax=winamax,
            fanduel=fanduel,
        )
        results.append(compared)
        on_progress(
            f"{index}/{anchors_total} — {compared['match']} : "
            f"{compared['comparable_count']} comparee(s), "
            f"{compared['fr_only_count']} FR seul"
        )

    payload = build_results_payload(
        results,
        partial=False,
        anchors_total=anchors_total,
        book_warnings=book_warnings,
    )
    output_path = output or (OUTPUT_DIR / "wnba_props_compare.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_progress_json(
        progress_json, results, partial=False, anchors_total=anchors_total
    )
    write_run_status_file(
        status_json,
        "success",
        f"Comparaison WNBA terminee — {len(results)}/{anchors_total} match(s).",
        match_filter=match_filter,
        results=results,
        anchors_total=anchors_total,
    )
    log.info(
        "WNBA compare terminé — %d match(s), %d comparable(s), %d FR seul, %d FD seul",
        payload["matches_done"],
        payload["comparable_count"],
        payload["fr_only_count"],
        payload["fd_only_count"],
    )
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare props WNBA FR vs FanDuel")
    parser.add_argument("--match", default="", help="Filtre texte sur le match")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=OUTPUT_DIR / "wnba_props_compare.json",
    )
    parser.add_argument(
        "--progress-json",
        type=Path,
        help="Ecrit les resultats partiels au fil de l'eau (JSON)",
    )
    parser.add_argument(
        "--status-json",
        type=Path,
        help="Met a jour le statut du run (JSON)",
    )
    args = parser.parse_args()

    if args.progress_json or args.status_json:
        run_live_compare(
            args.output,
            match_filter=args.match,
            progress_json=args.progress_json,
            status_json=args.status_json,
        )
        return

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
