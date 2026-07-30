"""Compare marchés baseball (MLB / KBO / NPB) — books FR vs FanDuel.

Pipeline séparé du tennis / basket.
"""

from __future__ import annotations

import argparse
import json
import logging
import threading
import time
from concurrent.futures import (
    FIRST_COMPLETED,
    ThreadPoolExecutor,
    TimeoutError as FuturesTimeout,
    as_completed,
    wait,
)
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from baseball_books_mapping import BOOK_NORMALIZERS, is_baseball_comparable_label, normalized_market_to_dict
from baseball_constants import BOOK_LABELS, COMPARABLE_FAMILIES
from baseball_market_mapping import (
    is_comparable_key,
    map_fanduel_market_to_entries,
    teams_match,
)
from basketball_props_anchor import assemble_anchor_result, flush_anchor_partial
from betclic_baseball_client import BetclicBaseballClient
from fanduel_baseball_client import FanDuelBaseballClient
from fanduel_client import (
    decimal_fr_to_american,
    format_american_moneyline,
    format_french_decimal,
    runner_fanduel_price_bundle,
)
from unibet_baseball_client import UnibetBaseballClient
from winamax_baseball_client import WinamaxBaseballClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("compare_baseball")

OUTPUT_DIR = Path(__file__).parent / "output"
WINAMAX_FETCH_TIMEOUT = 10
# Un match / book bloqué ne doit pas geler tout le run.
BOOK_STEP_TIMEOUT = 22.0
FD_STEP_TIMEOUT = 55.0
ANCHOR_TIMEOUT = 95.0
ANCHOR_MAX_WORKERS = 2


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_with_timeout(
    callback: Callable[[], Any],
    *,
    timeout: float,
    label: str,
) -> Any | None:
    """Execute un scrape avec timeout — None si dépassé (on passe à la suite)."""
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(callback)
        try:
            return future.result(timeout=timeout)
        except FuturesTimeout:
            log.warning("%s: timeout apres %.0fs — on passe", label, timeout)
            return None
        except Exception as exc:
            log.warning("%s: %s — on passe", label, exc)
            return None
    finally:
        pool.shutdown(wait=False)


def _skipped_anchor_result(match: str, *, reason: str) -> dict[str, Any]:
    return {
        "match": match,
        "sources": [],
        "fanduel_event_id": None,
        "comparable_count": 0,
        "fr_only_count": 0,
        "fd_only_count": 0,
        "fr_prop_market_count": 0,
        "fd_prop_market_count": 0,
        "comparables": [],
        "fr_only": [],
        "fd_only": [],
        "skipped": True,
        "skip_reason": reason,
    }


def _safe_call(label: str, callback: Callable[[], Any], fallback: Any) -> Any:
    try:
        return callback()
    except Exception as exc:
        log.warning("%s indisponible: %s", label, exc)
        return fallback


def merge_roster(*rosters: list[str] | None) -> list[str]:
    names: list[str] = []
    for roster in rosters:
        if not roster:
            continue
        for name in roster:
            text = str(name).strip()
            if text and text not in names:
                names.append(text)
    return names


def build_best_fr_map(
    book_events: dict[str, dict[str, Any]],
    *,
    home_team: str,
    away_team: str,
    roster: list[str],
) -> dict[str, dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for bookmaker, event in book_events.items():
        normalizer = BOOK_NORMALIZERS.get(bookmaker)
        if normalizer is None:
            continue
        for market in event.get("markets", []):
            label = str(market.get("label", "")).strip()
            if not is_baseball_comparable_label(label):
                continue
            outcomes = [(str(raw), odds) for raw, odds in market.get("outcomes", [])]
            for item in normalizer(
                label,
                outcomes,
                home_team=home_team,
                away_team=away_team,
                roster=roster,
            ):
                if item.market_family not in COMPARABLE_FAMILIES:
                    continue
                payload = normalized_market_to_dict(item)
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
                for outcome, odds in payload["outcomes"].items():
                    current = slot["outcomes"].get(outcome)
                    if current is None or float(odds) > float(current["odds"]):
                        slot["outcomes"][outcome] = {
                            "odds": float(odds),
                            "bookmaker": bookmaker,
                            "bookmaker_label": BOOK_LABELS.get(bookmaker, bookmaker),
                            "raw_outcome": outcome,
                        }
    return best


def build_fanduel_map(
    fanduel_event: dict[str, Any] | None,
    *,
    home_team: str,
    away_team: str,
    roster: list[str],
) -> dict[str, dict[str, Any]]:
    if not fanduel_event:
        return {}
    variant_map: dict[str, dict[str, Any]] = {}
    for market in fanduel_event.get("markets", []):
        for compare_key, outcome, market_label, runner in map_fanduel_market_to_entries(
            market,
            home_team=home_team,
            away_team=away_team,
            roster=roster,
        ):
            if not is_comparable_key(compare_key):
                continue
            bundle = runner_fanduel_price_bundle(runner)
            if bundle.get("decimal_fr") is None:
                continue
            slot = variant_map.setdefault(
                compare_key,
                {
                    "compare_key": compare_key,
                    "market_label": market_label,
                    "market_family": compare_key.split("|", 1)[0],
                    "outcomes": {},
                },
            )
            slot["outcomes"][outcome] = bundle
    return variant_map


def outcome_label_fr(outcome: str) -> str:
    mapping = {
        "Over": "Plus",
        "Under": "Moins",
        "Yes": "Oui",
        "home": "Domicile",
        "away": "Extérieur",
        "draw": "Nul",
    }
    return mapping.get(outcome, outcome)


def opposite_outcome(outcome: str) -> str | None:
    if outcome == "Over":
        return "Under"
    if outcome == "Under":
        return "Over"
    if outcome == "home":
        return "away"
    if outcome == "away":
        return "home"
    return None


def compute_paired_fields(
    *,
    outcome: str,
    fr_market: dict[str, Any],
    fd_market: dict[str, Any],
) -> dict[str, Any]:
    opposite = opposite_outcome(outcome)
    fields: dict[str, Any] = {
        "cote_fr_contraire": "",
        "bookmaker_fr_contraire": "",
        "cote_us_fanduel_contraire": "",
        "cote_fr_fanduel_contraire": "",
        "issue_fr_contraire": "",
        "paire_fd_complete": False,
    }
    if not opposite:
        return fields
    fields["issue_fr_contraire"] = outcome_label_fr(opposite)
    fr_opposite = fr_market["outcomes"].get(opposite)
    if fr_opposite:
        fields["cote_fr_contraire"] = format_french_decimal(float(fr_opposite["odds"]))
        fields["bookmaker_fr_contraire"] = fr_opposite.get("bookmaker_label", "")
    fd_side = fd_market["outcomes"].get(outcome)
    fd_opposite = fd_market["outcomes"].get(opposite)
    if fd_opposite:
        opp_american = fd_opposite.get("american")
        if opp_american is None and fd_opposite.get("decimal_fr") is not None:
            opp_american = decimal_fr_to_american(float(fd_opposite["decimal_fr"]))
        fields["cote_us_fanduel_contraire"] = format_american_moneyline(opp_american)
        if fd_opposite.get("decimal_fr") is not None:
            fields["cote_fr_fanduel_contraire"] = format_french_decimal(float(fd_opposite["decimal_fr"]))
    if (
        fd_side
        and fd_opposite
        and fd_side.get("decimal_fr") is not None
        and fd_opposite.get("decimal_fr") is not None
    ):
        fields["paire_fd_complete"] = True
    return fields


def format_ligne_baseball_fr(row: dict[str, Any], *, home_team: str = "", away_team: str = "") -> str:
    compare_key = str(row.get("compare_key", ""))
    parts = compare_key.split("|")
    family = parts[0] if parts else ""
    issue = outcome_label_fr(str(row.get("outcome", "")))
    player = str(row.get("player_name") or "")
    yes_families = {
        "hr_player",
        "runs_player",
        "hits_player",
        "rbi_player",
        "total_bases_player",
        "sb_player",
    }
    line = ""
    if family in yes_families:
        # keys: family|token or family|token|threshold
        if len(parts) >= 3:
            line = parts[-1].replace(".", ",")
        elif family == "runs_player" and len(parts) >= 2:
            line = parts[-1].replace(".", ",")
        elif family == "total_bases_player" and len(parts) >= 3:
            line = parts[-1].replace(".", ",")
    elif len(parts) >= 2 and family not in {"h2h", "f5_h2h", "inning1_result"}:
        line = parts[-1].replace(".", ",")
    labels = {
        "h2h": "vainqueur",
        "run_line": "handicap runs",
        "runs_total": "total runs",
        "runs_team": "total runs équipe",
        "f5_h2h": "vainqueur F5",
        "f5_run_line": "handicap F5",
        "f5_runs_total": "total runs F5",
        "inning1_result": "1ère manche",
        "inning1_runs_total": "runs 1ère manche",
        "hr_player": "home run",
        "runs_player": "runs joueur",
        "hits_player": "hits",
        "rbi_player": "RBI",
        "total_bases_player": "total bases",
        "sb_player": "stolen bases",
        "strikeouts_pitcher": "strikeouts",
    }
    stat = labels.get(family, family)
    side_name = ""
    if str(row.get("outcome")) == "home" and home_team:
        side_name = home_team
    elif str(row.get("outcome")) == "away" and away_team:
        side_name = away_team
    if family in {"h2h", "f5_h2h", "inning1_result", "run_line", "f5_run_line"} and side_name:
        if line and family in {"run_line", "f5_run_line"}:
            return f"{side_name} ({stat} {line})"
        return f"{side_name} — {stat}"
    if family == "hr_player" and player:
        thr = line or "1"
        return f"Oui {thr}+ HR — {player}" if thr not in {"1", "1,0"} else f"Oui HR — {player}"
    if family == "runs_player" and player:
        return f"Oui {line or '1'}+ runs — {player}"
    if family == "hits_player" and player:
        return f"Oui {line or '1'}+ hits — {player}"
    if family == "rbi_player" and player:
        return f"Oui {line or '1'}+ RBI — {player}"
    if family == "total_bases_player" and player and line:
        return f"Oui {line}+ total bases — {player}"
    if family == "sb_player" and player:
        return f"Oui {line or '1'}+ SB — {player}"
    if family == "strikeouts_pitcher" and player and line:
        return f"{issue} de {line} K — {player}"
    if player and line:
        return f"{issue} de {line} {stat} — {player}"
    if line:
        return f"{issue} de {line} {stat}"
    return str(row.get("fr_market_label") or compare_key)


def enrich_comparable_row(
    row: dict[str, Any],
    *,
    home_team: str = "",
    away_team: str = "",
) -> dict[str, Any]:
    fr_odds = round(float(row["best_fr_odds"]), 2)
    fd_decimal = round(float(row["fanduel_odds"]), 2)
    price_delta = round(fr_odds - fd_decimal, 2)
    if price_delta > 0:
        best_side = "fr"
    elif price_delta < 0:
        best_side = "fanduel"
    else:
        best_side = "tie"
    return {
        **row,
        "best_side": best_side,
        "cote_fr": format_french_decimal(fr_odds),
        "bookmaker_fr": row.get("best_fr_bookmaker", ""),
        "cote_us_fanduel_ml": format_american_moneyline(row.get("fanduel_american")),
        "cote_fr_fanduel": format_french_decimal(fd_decimal),
        "ecart_fr_moins_fd": f"{price_delta:+.2f}".replace(".", ","),
        "meilleur_cote": "FR" if best_side == "fr" else "FanDuel" if best_side == "fanduel" else "Egalite",
        "issue_fr": outcome_label_fr(str(row.get("outcome", ""))),
        "marche_fr": str(row.get("fr_market_label", "")),
        "marche_fanduel": str(row.get("fanduel_market_label", "")),
        "ligne_props_fr": format_ligne_baseball_fr(row, home_team=home_team, away_team=away_team),
    }


def enrich_fr_only_row(
    row: dict[str, Any],
    *,
    home_team: str = "",
    away_team: str = "",
) -> dict[str, Any]:
    return {
        **row,
        "cote_fr": format_french_decimal(float(row["best_fr_odds"])),
        "bookmaker_fr": row.get("best_fr_bookmaker", ""),
        "cote_us_fanduel_ml": "",
        "cote_fr_fanduel": "",
        "ecart_fr_moins_fd": "",
        "meilleur_cote": "FR seul",
        "issue_fr": outcome_label_fr(str(row.get("outcome", ""))),
        "marche_fr": str(row.get("fr_market_label", "")),
        "marche_fanduel": "",
        "ligne_props_fr": format_ligne_baseball_fr(row, home_team=home_team, away_team=away_team),
    }


def enrich_fd_only_row(
    row: dict[str, Any],
    *,
    home_team: str = "",
    away_team: str = "",
) -> dict[str, Any]:
    return {
        **row,
        "cote_fr": "",
        "bookmaker_fr": "",
        "cote_us_fanduel_ml": row.get("cote_us_fanduel_ml", ""),
        "cote_fr_fanduel": row.get("cote_fr_fanduel", ""),
        "ecart_fr_moins_fd": "",
        "meilleur_cote": "FanDuel seul",
        "issue_fr": outcome_label_fr(str(row.get("outcome", ""))),
        "marche_fr": "",
        "marche_fanduel": str(row.get("fanduel_market_label", "")),
        "ligne_props_fr": format_ligne_baseball_fr(row, home_team=home_team, away_team=away_team),
    }


def compare_normalized_markets(
    fr_map: dict[str, dict[str, Any]],
    fd_map: dict[str, dict[str, Any]],
    *,
    home_team: str = "",
    away_team: str = "",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for compare_key, fr_market in fr_map.items():
        if not is_comparable_key(compare_key):
            continue
        fd_market = fd_map.get(compare_key)
        if not fd_market:
            continue
        for outcome, fr_payload in fr_market["outcomes"].items():
            fd_bundle = fd_market["outcomes"].get(outcome)
            if not fd_bundle or fd_bundle.get("decimal_fr") is None:
                continue
            rows.append(
                enrich_comparable_row(
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
                        **compute_paired_fields(
                            outcome=outcome,
                            fr_market=fr_market,
                            fd_market=fd_market,
                        ),
                    },
                    home_team=home_team,
                    away_team=away_team,
                )
            )
    return rows


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

    def ensure_anchor(home: str, away: str, competition: str = "") -> dict[str, Any]:
        key = anchor_key(home, away)
        if key not in anchors:
            anchors[key] = {
                "home_team": home,
                "away_team": away,
                "match": f"{home} vs {away}",
                "competition": competition or "",
                "sources": set(),
                "urls": {},
                "unibet_event_id": None,
                "betclic_match_id": None,
                "winamax_match_id": None,
                "fanduel_event_id": None,
            }
        elif competition and not anchors[key].get("competition"):
            anchors[key]["competition"] = competition
        return anchors[key]

    for event in unibet_events:
        anchor = ensure_anchor(event.home_team, event.away_team, getattr(event, "competition", ""))
        anchor["sources"].add("unibet")
        anchor["urls"]["unibet"] = event.url
        anchor["unibet_event_id"] = event.event_id

    for link in betclic_links:
        matched = None
        for key, anchor in anchors.items():
            if teams_match(anchor["home_team"], anchor["away_team"], link.home_team, link.away_team):
                matched = key
                break
        if matched is None:
            anchor = ensure_anchor(link.home_team, link.away_team, getattr(link, "competition", ""))
        else:
            anchor = anchors[matched]
        anchor["sources"].add("betclic")
        anchor["urls"]["betclic"] = link.url
        anchor["betclic_match_id"] = link.match_id
        if getattr(link, "competition", ""):
            anchor["competition"] = link.competition

    for link in winamax_links:
        matched = None
        for key, anchor in anchors.items():
            if teams_match(anchor["home_team"], anchor["away_team"], link.home_team, link.away_team):
                matched = key
                break
        if matched is None:
            anchor = ensure_anchor(link.home_team, link.away_team, getattr(link, "competition", ""))
        else:
            anchor = anchors[matched]
        anchor["sources"].add("winamax")
        anchor["urls"]["winamax"] = link.url
        anchor["winamax_match_id"] = link.match_id
        if getattr(link, "competition", ""):
            anchor["competition"] = link.competition

    for event in fanduel_events:
        matched_key = None
        for key, anchor in anchors.items():
            if teams_match(anchor["home_team"], anchor["away_team"], event.home_team, event.away_team):
                matched_key = key
                break
        if matched_key is None:
            anchor = ensure_anchor(event.home_team, event.away_team, getattr(event, "competition", ""))
        else:
            anchor = anchors[matched_key]
        anchor["sources"].add("fanduel")
        anchor["fanduel_event_id"] = event.event_id
        if getattr(event, "competition", ""):
            anchor["competition"] = event.competition
        if matched_key is not None:
            if teams_match(anchor["home_team"], anchor["away_team"], event.home_team, event.away_team):
                if teams_match(anchor["home_team"], event.home_team, event.home_team, event.home_team):
                    pass

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
    return [
        {
            "match": result.get("match", ""),
            "comparable_count": int(result.get("comparable_count", 0)),
            "fr_only_count": int(result.get("fr_only_count", 0)),
            "fd_only_count": int(result.get("fd_only_count", 0)),
            "fr_market_count": int(result.get("fr_prop_market_count", 0)),
            "fd_market_count": int(result.get("fd_prop_market_count", 0)),
            "fanduel_found": bool(result.get("fanduel_event_id")),
        }
        for result in results
    ]


def build_results_payload(
    results: list[dict[str, Any]],
    *,
    partial: bool,
    anchors_total: int | None = None,
    book_warnings: list[str] | None = None,
    include_fd_only_rows: bool = False,
    max_fr_only_rows: int | None = 200,
) -> dict[str, Any]:
    comparable_rows = collect_comparable_rows(results)
    fr_higher_rows = collect_fr_higher_rows(comparable_rows)
    fr_only_rows = collect_fr_only_rows(results)
    fd_only_rows = collect_fd_only_rows(results)
    match_progress = build_match_progress(results)
    fr_only_export = fr_only_rows[:max_fr_only_rows] if max_fr_only_rows is not None else fr_only_rows
    return {
        "source": "baseball_markets_comparable",
        "generated_at": utc_now(),
        "partial": partial,
        "anchors_total": anchors_total if anchors_total is not None else len(match_progress),
        "matches_done": len(match_progress),
        "comparable_count": len(comparable_rows),
        "fr_higher_count": len(fr_higher_rows),
        "value_count": 0,
        "fr_only_count": len(fr_only_rows),
        "fd_only_count": len(fd_only_rows),
        "fd_event_count": sum(1 for result in results if int(result.get("fd_prop_market_count", 0)) > 0),
        "fr_event_count": sum(1 for result in results if int(result.get("fr_prop_market_count", 0)) > 0),
        "comparables": comparable_rows,
        "fr_higher_comparables": fr_higher_rows,
        "value_comparables": [],
        "fr_only_comparables": fr_only_export,
        "fd_only_comparables": fd_only_rows if include_fd_only_rows else [],
        "match_progress": match_progress,
        "notes": [
            "Pipeline baseball (MLB + KBO + NPB) séparé du tennis / basket.",
            "Référence US: FanDuel (game lines + props joueur).",
            "Books FR: Unibet, Betclic, Winamax — meilleure cote par compare_key.",
            "Betclic soft-fail si 403 (IP hors FR) — Unibet/Winamax continuent.",
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
    payload = build_results_payload(
        results,
        partial=partial,
        anchors_total=anchors_total,
        include_fd_only_rows=False,
    )
    from atomic_json import write_json_atomic

    try:
        write_json_atomic(path, payload, compact=True)
    except OSError as exc:
        log.warning("Progress JSON non ecrit (%s): %s", path.name, exc)


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
        "sport": "baseball",
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


def fetch_live_listings(
    *,
    unibet: UnibetBaseballClient,
    betclic: BetclicBaseballClient,
    winamax: WinamaxBaseballClient,
    fanduel: FanDuelBaseballClient,
    on_status: Callable[[str], None] | None = None,
) -> tuple[list[Any], list[Any], list[Any], list[Any], list[str]]:
    def status(message: str) -> None:
        if on_status is not None:
            on_status(message)

    warnings: list[str] = []
    status("Chargement parallele des calendriers baseball (MLB/KBO/NPB)...")
    with ThreadPoolExecutor(max_workers=4) as pool:
        fut_unibet = pool.submit(unibet.list_baseball_events)
        fut_betclic = pool.submit(betclic.list_baseball_matches)
        fut_winamax = pool.submit(winamax.list_baseball_matches)
        fut_fanduel = pool.submit(fanduel.list_baseball_events)
        unibet_events = _safe_call("Unibet", fut_unibet.result, [])
        betclic_links = _safe_call("Betclic", fut_betclic.result, [])
        winamax_links = _safe_call("Winamax", fut_winamax.result, [])
        fanduel_events = _safe_call("FanDuel", fut_fanduel.result, [])

    if not unibet_events:
        warnings.append("Unibet: aucun match baseball ou scrape indisponible.")
    if not betclic_links:
        warnings.append("Betclic: aucun match baseball ou scrape indisponible (souvent 403 hors FR).")
    if not winamax_links:
        warnings.append("Winamax: aucun match baseball ou scrape indisponible.")
    if not fanduel_events:
        warnings.append("FanDuel: aucun evenement baseball ou scrape indisponible.")
    status(
        "Calendriers baseball — "
        f"Unibet {len(unibet_events)}, Betclic {len(betclic_links)}, "
        f"Winamax {len(winamax_links)}, FanDuel {len(fanduel_events)}"
    )
    return unibet_events, betclic_links, winamax_links, fanduel_events, warnings


def attach_capture_times(
    rows: list[dict[str, Any]],
    *,
    fr_scraped_at: str | None = None,
    fd_scraped_at: str | None = None,
) -> list[dict[str, Any]]:
    for row in rows:
        if fr_scraped_at:
            row["fr_captured_at"] = fr_scraped_at
        if fd_scraped_at:
            row["fd_captured_at"] = fd_scraped_at
        row["captured_at"] = fd_scraped_at or fr_scraped_at or utc_now()
    return rows


def compare_anchor(
    anchor: dict[str, Any],
    *,
    unibet_events: list[Any],
    betclic_links: list[Any],
    winamax_links: list[Any],
    fanduel_events: list[Any],
    unibet: UnibetBaseballClient,
    betclic: BetclicBaseballClient,
    winamax: WinamaxBaseballClient,
    fanduel: FanDuelBaseballClient,
    on_partial: Callable[[dict[str, Any], str], None] | None = None,
) -> dict[str, Any]:
    book_events: dict[str, dict[str, Any]] = {}
    home_team = anchor["home_team"]
    away_team = anchor["away_team"]
    # Prefer FanDuel home/away orientation when available (Away @ Home naming).
    fanduel_event_meta = None
    if anchor.get("fanduel_event_id"):
        fanduel_event_meta = next(
            (item for item in fanduel_events if item.event_id == anchor["fanduel_event_id"]),
            None,
        )
    if fanduel_event_meta is not None:
        home_team = fanduel_event_meta.home_team
        away_team = fanduel_event_meta.away_team
    roster = merge_roster([], [home_team, away_team])
    fr_map: dict[str, dict[str, Any]] = {}
    fd_map: dict[str, dict[str, Any]] = {}
    fr_scraped_at: str | None = None
    fd_scraped_at: str | None = None
    fanduel_payload: dict[str, Any] | None = None

    def enrich_fr(row: dict[str, Any]) -> dict[str, Any]:
        return enrich_fr_only_row(row, home_team=home_team, away_team=away_team)

    def enrich_fd(row: dict[str, Any]) -> dict[str, Any]:
        return enrich_fd_only_row(row, home_team=home_team, away_team=away_team)

    def compare_fn(fr: dict[str, dict[str, Any]], fd: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        return compare_normalized_markets(fr, fd, home_team=home_team, away_team=away_team)

    def flush(step: str) -> None:
        flush_anchor_partial(
            anchor,
            book_events=book_events,
            roster=roster,
            fr_map=fr_map,
            fd_map=fd_map,
            fr_scraped_at=fr_scraped_at,
            fd_scraped_at=fd_scraped_at,
            step=step,
            on_partial=on_partial,
            compare_normalized_props=compare_fn,
            enrich_fr_only_row=enrich_fr,
            enrich_fd_only_row=enrich_fd,
            attach_capture_times=attach_capture_times,
        )

    book_lock = threading.Lock()

    def ingest_fr_book(book: str, payload: dict[str, Any] | None) -> None:
        nonlocal roster, fr_scraped_at, fr_map
        if not payload:
            return
        with book_lock:
            book_events[book] = payload
            roster = merge_roster(
                book_events.get("winamax", {}).get("roster"),
                book_events.get("betclic", {}).get("roster"),
                book_events.get("unibet", {}).get("roster"),
                [home_team, away_team],
            )
            fr_scraped_at = utc_now()
            fr_map = build_best_fr_map(
                book_events,
                home_team=home_team,
                away_team=away_team,
                roster=roster,
            )
            if fanduel_payload is not None:
                fd_map.update(
                    build_fanduel_map(
                        fanduel_payload,
                        home_team=home_team,
                        away_team=away_team,
                        roster=roster,
                    )
                )
            flush(book)

    def ingest_fanduel(payload: dict[str, Any] | None) -> None:
        nonlocal roster, fd_scraped_at, fd_map, fanduel_payload
        if not payload:
            return
        with book_lock:
            fanduel_payload = payload
            fd_scraped_at = utc_now()
            roster = merge_roster(roster, [home_team, away_team])
            fd_map = build_fanduel_map(
                payload,
                home_team=home_team,
                away_team=away_team,
                roster=roster,
            )
            flush("fanduel")

    unibet_event = next(
        (item for item in unibet_events if item.event_id == anchor.get("unibet_event_id")),
        None,
    )
    betclic_link = next(
        (item for item in betclic_links if item.match_id == anchor.get("betclic_match_id")),
        None,
    )
    winamax_link = next(
        (item for item in winamax_links if item.match_id == anchor.get("winamax_match_id")),
        None,
    )
    fanduel_event = None
    if anchor.get("fanduel_event_id"):
        fanduel_event = next(
            (item for item in fanduel_events if item.event_id == anchor["fanduel_event_id"]),
            None,
        )

    priority_jobs: list[tuple[str, Callable[[], dict[str, Any] | None]]] = []
    if fanduel_event:
        priority_jobs.append(
            (
                "fanduel",
                lambda event=fanduel_event: _run_with_timeout(
                    lambda: fanduel.build_event_payload(event),
                    timeout=FD_STEP_TIMEOUT,
                    label=f"FanDuel {anchor['match']}",
                ),
            )
        )
    if unibet_event:
        priority_jobs.append(
            (
                "unibet",
                lambda event=unibet_event: _run_with_timeout(
                    lambda: unibet.build_event_payload(event),
                    timeout=BOOK_STEP_TIMEOUT,
                    label=f"Unibet {anchor['match']}",
                ),
            )
        )
    if betclic_link:
        priority_jobs.append(
            (
                "betclic",
                lambda link=betclic_link: _run_with_timeout(
                    lambda: betclic.build_event_payload(link),
                    timeout=BOOK_STEP_TIMEOUT,
                    label=f"Betclic {anchor['match']}",
                ),
            )
        )
    if winamax_link:
        priority_jobs.append(
            (
                "winamax",
                lambda link=winamax_link: _run_with_timeout(
                    lambda: winamax.build_event_payload(link),
                    timeout=BOOK_STEP_TIMEOUT,
                    label=f"Winamax {anchor['match']}",
                ),
            )
        )

    if priority_jobs:
        with ThreadPoolExecutor(max_workers=min(4, len(priority_jobs))) as pool:
            futures = {pool.submit(job[1]): job[0] for job in priority_jobs}
            for future in as_completed(futures):
                book = futures[future]
                try:
                    payload = future.result(timeout=FD_STEP_TIMEOUT + 5)
                except Exception as exc:
                    log.warning("%s ignore %s: %s", book, anchor["match"], exc)
                    continue
                if book == "fanduel":
                    ingest_fanduel(payload)
                else:
                    ingest_fr_book(book, payload)

    return assemble_anchor_result(
        anchor,
        book_events=book_events,
        roster=roster,
        fr_map=fr_map,
        fd_map=fd_map,
        fr_scraped_at=fr_scraped_at,
        fd_scraped_at=fd_scraped_at,
        compare_normalized_props=compare_fn,
        enrich_fr_only_row=enrich_fr,
        enrich_fd_only_row=enrich_fd,
        attach_capture_times=attach_capture_times,
    )


def run_compare(*, match_filter: str = "") -> dict[str, Any]:
    unibet = UnibetBaseballClient()
    betclic = BetclicBaseballClient()
    winamax = WinamaxBaseballClient(fetch_timeout=WINAMAX_FETCH_TIMEOUT)
    fanduel = FanDuelBaseballClient()
    unibet_events, betclic_links, winamax_links, fanduel_events, book_warnings = fetch_live_listings(
        unibet=unibet,
        betclic=betclic,
        winamax=winamax,
        fanduel=fanduel,
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
        include_fd_only_rows=True,
    )


def run_live_compare(
    output: Path | None = None,
    *,
    match_filter: str = "",
    progress_json: Path | None = None,
    status_json: Path | None = None,
) -> Path:
    unibet = UnibetBaseballClient()
    betclic = BetclicBaseballClient()
    winamax = WinamaxBaseballClient(fetch_timeout=WINAMAX_FETCH_TIMEOUT)
    fanduel = FanDuelBaseballClient()

    write_run_status_file(status_json, "running", "Chargement des matchs baseball...", match_filter=match_filter)
    write_progress_json(progress_json, [], partial=True)

    def on_listing_status(message: str) -> None:
        write_run_status_file(status_json, "running", message, match_filter=match_filter)

    unibet_events, betclic_links, winamax_links, fanduel_events, book_warnings = fetch_live_listings(
        unibet=unibet,
        betclic=betclic,
        winamax=winamax,
        fanduel=fanduel,
        on_status=on_listing_status,
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
        f"{anchors_total} match(s) baseball — resultats au fil de l'eau...",
        match_filter=match_filter,
        anchors_total=anchors_total,
    )
    write_progress_json(progress_json, [], partial=True, anchors_total=anchors_total)

    results: list[dict[str, Any]] = []
    progress_lock = threading.Lock()
    partial_by_match: dict[str, dict[str, Any]] = {}
    done_count = 0

    def notify(message: str) -> None:
        with progress_lock:
            snapshot = list(results)
            for partial in partial_by_match.values():
                if all(item.get("match") != partial.get("match") for item in snapshot):
                    snapshot.append(partial)
            write_progress_json(progress_json, snapshot, partial=True, anchors_total=anchors_total)
            write_run_status_file(
                status_json,
                "running",
                message,
                match_filter=match_filter,
                results=snapshot,
                anchors_total=anchors_total,
            )

    def make_on_partial(match_key: str, index: int) -> Callable[[dict[str, Any], str], None]:
        def _on_partial(partial: dict[str, Any], step: str) -> None:
            with progress_lock:
                partial_by_match[match_key] = partial
            notify(
                f"{index}/{anchors_total} — {match_key} ({step}) — "
                f"{partial.get('comparable_count', 0)} comparee(s), "
                f"{partial.get('fr_only_count', 0)} FR seul"
            )

        return _on_partial

    with ThreadPoolExecutor(max_workers=min(ANCHOR_MAX_WORKERS, max(1, len(anchors)))) as pool:
        queue = list(enumerate(anchors, start=1))
        futures: dict[Any, tuple[int, dict[str, Any]]] = {}
        started_at: dict[Any, float] = {}

        def submit_one(index: int, anchor: dict[str, Any]) -> None:
            match_key = anchor["match"]
            future = pool.submit(
                compare_anchor,
                anchor,
                unibet_events=unibet_events,
                betclic_links=betclic_links,
                winamax_links=winamax_links,
                fanduel_events=fanduel_events,
                unibet=unibet,
                betclic=betclic,
                winamax=winamax,
                fanduel=fanduel,
                on_partial=make_on_partial(match_key, index),
            )
            futures[future] = (index, anchor)
            started_at[future] = time.monotonic()

        while queue and len(futures) < ANCHOR_MAX_WORKERS:
            index, anchor = queue.pop(0)
            submit_one(index, anchor)

        while futures or queue:
            if not futures:
                while queue and len(futures) < ANCHOR_MAX_WORKERS:
                    index, anchor = queue.pop(0)
                    submit_one(index, anchor)
                continue

            done, _still = wait(set(futures), timeout=1.0, return_when=FIRST_COMPLETED)
            now = time.monotonic()

            timed_out = [
                future
                for future in list(futures)
                if future not in done and now - started_at[future] >= ANCHOR_TIMEOUT
            ]
            for future in timed_out:
                index, anchor = futures.pop(future)
                started_at.pop(future, None)
                match_key = anchor["match"]
                log.warning(
                    "Match timeout %s apres %.0fs — on passe au suivant",
                    match_key,
                    ANCHOR_TIMEOUT,
                )
                with progress_lock:
                    partial_by_match.pop(match_key, None)
                    results.append(
                        _skipped_anchor_result(
                            match_key,
                            reason=f"timeout apres {ANCHOR_TIMEOUT:.0f}s",
                        )
                    )
                    done_count = len(results)
                notify(f"{done_count}/{anchors_total} — {match_key} — timeout, passe au suivant")
                if queue:
                    next_index, next_anchor = queue.pop(0)
                    submit_one(next_index, next_anchor)

            for future in done:
                index, anchor = futures.pop(future, (0, {}))
                started_at.pop(future, None)
                if not anchor:
                    continue
                match_key = anchor["match"]
                try:
                    compared = future.result()
                except Exception as exc:
                    log.warning("Match %s erreur: %s", match_key, exc)
                    compared = _skipped_anchor_result(match_key, reason=str(exc))
                with progress_lock:
                    partial_by_match.pop(match_key, None)
                    results.append(compared)
                    done_count = len(results)
                notify(
                    f"{done_count}/{anchors_total} — {match_key} — "
                    f"{compared.get('comparable_count', 0)} comparee(s)"
                )
                if queue:
                    next_index, next_anchor = queue.pop(0)
                    submit_one(next_index, next_anchor)

    payload = build_results_payload(
        results,
        partial=False,
        anchors_total=anchors_total,
        book_warnings=book_warnings,
        include_fd_only_rows=True,
    )
    out = output or (OUTPUT_DIR / "baseball_compare.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if progress_json:
        write_progress_json(progress_json, results, partial=False, anchors_total=anchors_total)
    write_run_status_file(
        status_json,
        "success",
        (
            f"Terminé — {payload['matches_done']} match(s), "
            f"{payload['comparable_count']} comparable(s), "
            f"{payload['fr_higher_count']} FR plus haut"
        ),
        match_filter=match_filter,
        results=results,
        anchors_total=anchors_total,
    )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare marchés baseball FR vs FanDuel")
    parser.add_argument("--match", default="", help="Filtre texte sur le match")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=OUTPUT_DIR / "baseball_compare.json",
    )
    parser.add_argument("--progress-json", type=Path)
    parser.add_argument("--status-json", type=Path)
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
        "Baseball compare terminé — %d match(s), %d comparable(s), %d FR seul, %d FD seul",
        payload["matches_done"],
        payload["comparable_count"],
        payload["fr_only_count"],
        payload["fd_only_count"],
    )


if __name__ == "__main__":
    main()
