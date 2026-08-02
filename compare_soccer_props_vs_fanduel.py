"""Compare props foot (buteur / décisif / tirs…) — books FR vs FanDuel."""

from __future__ import annotations

import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_json import write_json_atomic
from betclic_soccer_client import BetclicSoccerClient
from basketball_props_anchor import assemble_anchor_result
from book_urls import selection_id_for_normalized_outcome
from fanduel_client import (
    format_american_moneyline,
    format_french_decimal,
)
from fanduel_soccer_client import FanDuelSoccerClient
from soccer_books_mapping import BOOK_NORMALIZERS, is_soccer_player_prop_label, normalized_market_to_dict
from soccer_constants import BOOK_LABELS, FAMILY_LABELS_FR
from soccer_market_mapping import (
    format_soccer_ligne,
    is_comparable_soccer_key,
    map_fanduel_soccer_market,
)
from unibet_soccer_client import UnibetSoccerClient
from winamax_soccer_client import WinamaxSoccerClient, WinamaxSoccerMatchLink

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("compare_soccer")

OUTPUT_DIR = Path(__file__).parent / "output"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def teams_match(home_a: str, away_a: str, home_b: str, away_b: str) -> bool:
    from soccer_market_mapping import soccer_teams_match

    return soccer_teams_match(home_a, away_a, home_b, away_b)


def build_best_fr_map(
    book_events: dict[str, dict[str, Any]],
    *,
    roster: list[str],
    home_team: str = "",
    away_team: str = "",
) -> dict[str, dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for bookmaker, event in book_events.items():
        normalizer = BOOK_NORMALIZERS.get(bookmaker)
        if not normalizer:
            continue
        home = str(event.get("home_team") or home_team or "")
        away = str(event.get("away_team") or away_team or "")
        for market in event.get("markets", []):
            label = str(market.get("label", "")).strip()
            if not is_soccer_player_prop_label(label):
                continue
            outcomes = [(str(raw), odds) for raw, odds in market.get("outcomes", [])]
            selection_ids = market.get("selection_ids") or {}
            for item in normalizer(label, outcomes, roster, home_team=home, away_team=away):
                payload = normalized_market_to_dict(item)
                for outcome, odds in payload["outcomes"].items():
                    slot = best.setdefault(
                        item.compare_key,
                        {
                            "compare_key": item.compare_key,
                            "market_family": item.market_family,
                            "market_label_raw": item.market_label_raw,
                            "player_name": item.player_name,
                            "outcomes": {},
                        },
                    )
                    if not slot.get("player_name"):
                        slot["player_name"] = item.player_name
                    current = slot["outcomes"].get(outcome)
                    if current is None or float(odds) > float(current["odds"]):
                        slot["outcomes"][outcome] = {
                            "odds": float(odds),
                            "bookmaker": bookmaker,
                            "bookmaker_label": BOOK_LABELS.get(bookmaker, bookmaker),
                            "raw_outcome": outcome,
                            "selection_id": selection_id_for_normalized_outcome(
                                normalized_outcome=str(outcome),
                                raw_outcomes=outcomes,
                                selection_ids=selection_ids,
                                home=home,
                                away=away,
                            )
                            if bookmaker == "unibet"
                            else "",
                        }
    return best


def build_fanduel_map(
    fanduel_event: dict[str, Any] | None,
    *,
    roster: list[str],
    captured_at: str | None = None,
) -> dict[str, dict[str, Any]]:
    if not fanduel_event:
        return {}
    variant_map: dict[str, dict[str, Any]] = {}
    home = str(fanduel_event.get("home_team") or "")
    away = str(fanduel_event.get("away_team") or "")
    for market in fanduel_event.get("markets", []):
        mapped = map_fanduel_soccer_market(
            market,
            roster=roster,
            home_team=home,
            away_team=away,
        )
        if not mapped:
            continue
        market_label = str(market.get("marketName", ""))
        runners_by_name = {
            str(rr.get("runnerName") or "").strip(): rr for rr in (market.get("runners") or [])
        }
        for compare_key, family, player_name, outcome, runner_name in mapped:
            runner = runners_by_name.get(runner_name)
            if runner is None:
                continue
            bundle = FanDuelSoccerClient.runner_bundle(runner)
            if not bundle or bundle.get("decimal_fr") is None:
                continue
            slot = variant_map.setdefault(
                compare_key,
                {
                    "compare_key": compare_key,
                    "market_label": market_label,
                    "market_family": family,
                    "player_name": player_name,
                    "source": "fanduel",
                    "source_label": "FanDuel",
                    "source_bookmaker": "FanDuel",
                    "captured_at": captured_at or "",
                    "outcomes": {},
                },
            )
            slot["outcomes"][outcome] = bundle
    return variant_map


def enrich_comparable_row(row: dict[str, Any]) -> dict[str, Any]:
    fr_odds = float(row["best_fr_odds"])
    fd_odds = float(row["fanduel_odds"])
    ecart = fr_odds - fd_odds
    best_side = "fr" if fr_odds > fd_odds else ("fd" if fd_odds > fr_odds else "eq")
    family = str(row.get("market_family") or "")
    player = str(row.get("player_name") or "")
    outcome = str(row.get("outcome") or "Yes")
    ligne = format_soccer_ligne(
        family=family,
        player_name=player,
        outcome=outcome,
        compare_key=str(row.get("compare_key") or ""),
    )
    return {
        **row,
        "bookmaker_fr": row.get("best_fr_bookmaker", ""),
        "cote_fr": format_french_decimal(fr_odds),
        "cote_us_fanduel_ml": format_american_moneyline(row.get("fanduel_american")),
        "cote_fr_fanduel": format_french_decimal(fd_odds),
        "ecart_fr_moins_fd": format_french_decimal(ecart),
        "meilleur_cote": "FR" if best_side == "fr" else ("US" if best_side == "fd" else "="),
        "best_side": best_side,
        "issue_fr": "Oui" if outcome == "Yes" else outcome,
        "marche_fr": row.get("fr_market_label") or FAMILY_LABELS_FR.get(family, family),
        "marche_fanduel": row.get("fanduel_market_label") or "",
        "ligne_props_fr": ligne,
        "us_source": row.get("us_source", "fanduel"),
        "us_source_label": row.get("us_source_label", "FanDuel"),
        "us_bookmaker": row.get("us_bookmaker", "FanDuel"),
    }


def enrich_fr_only_row(row: dict[str, Any]) -> dict[str, Any]:
    family = str(row.get("market_family") or "")
    player = str(row.get("player_name") or "")
    outcome = str(row.get("outcome") or "Yes")
    return {
        **row,
        "bookmaker_fr": row.get("best_fr_bookmaker", ""),
        "cote_fr": format_french_decimal(float(row["best_fr_odds"])),
        "cote_us_fanduel_ml": "",
        "cote_fr_fanduel": "",
        "ecart_fr_moins_fd": "",
        "meilleur_cote": "FR seul",
        "issue_fr": "Oui" if outcome == "Yes" else outcome,
        "marche_fr": row.get("fr_market_label") or FAMILY_LABELS_FR.get(family, family),
        "marche_fanduel": "",
        "ligne_props_fr": format_soccer_ligne(
            family=family,
            player_name=player,
            outcome=outcome,
            compare_key=str(row.get("compare_key") or ""),
        ),
    }


def enrich_fd_only_row(row: dict[str, Any]) -> dict[str, Any]:
    family = str(row.get("market_family") or "")
    player = str(row.get("player_name") or "")
    outcome = str(row.get("outcome") or "Yes")
    us_label = row.get("us_source_label") or "FanDuel"
    return {
        **row,
        "bookmaker_fr": "",
        "cote_fr": "",
        "cote_us_fanduel_ml": row.get("cote_us_fanduel_ml", ""),
        "cote_fr_fanduel": row.get("cote_fr_fanduel", ""),
        "ecart_fr_moins_fd": "",
        "meilleur_cote": f"{us_label} seul",
        "issue_fr": "Oui" if outcome == "Yes" else outcome,
        "marche_fr": "",
        "marche_fanduel": row.get("fanduel_market_label") or "",
        "ligne_props_fr": format_soccer_ligne(
            family=family,
            player_name=player,
            outcome=outcome,
            compare_key=str(row.get("compare_key") or ""),
        ),
    }


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
            row["us_captured_at"] = fd_scraped_at
        row["captured_at"] = fd_scraped_at or fr_scraped_at or ""
    return rows


def compare_normalized_props(
    fr_map: dict[str, dict[str, Any]],
    fd_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for compare_key, fr_market in fr_map.items():
        if not is_comparable_soccer_key(compare_key):
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
                        "selection_id": fr_payload.get("selection_id", ""),
                        "fanduel_american": fd_bundle.get("american"),
                        "fanduel_odds": float(fd_bundle.get("decimal_raw") or fd_bundle["decimal_fr"]),
                        "us_source": fd_market.get("source", "fanduel"),
                        "us_source_label": fd_market.get("source_label", "FanDuel"),
                        "us_bookmaker": fd_market.get("source_bookmaker", "FanDuel"),
                        "us_captured_at": fd_market.get("captured_at", ""),
                    }
                )
            )
    return rows


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


def roster_from_markets(markets: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for market in markets:
        label = str(market.get("label") or market.get("marketName") or "")
        if not is_soccer_player_prop_label(label) and "Goalscorer" not in label and "Assist" not in label and "Shots" not in label:
            # still collect FD runner names below
            pass
        for outcome in market.get("outcomes") or []:
            if isinstance(outcome, (list, tuple)) and outcome:
                name = str(outcome[0]).strip()
                if name and "/" not in name and name not in names:
                    names.append(name)
        for runner in market.get("runners") or []:
            name = str(runner.get("runnerName") or "").strip()
            if name and name not in names:
                names.append(name)
    return names


def anchor_matches_filter(anchor: dict[str, Any], needle: str) -> bool:
    """Filtre équipe OU ligue/compétition (sous-chaine, case-insensitive)."""
    text = needle.strip().lower()
    if not text:
        return True
    urls = anchor.get("urls") or {}
    blob = " ".join(
        [
            str(anchor.get("match") or ""),
            str(anchor.get("home_team") or ""),
            str(anchor.get("away_team") or ""),
            str(anchor.get("competition") or ""),
            str(anchor.get("fanduel_competition") or ""),
            str(anchor.get("winamax_competition") or ""),
            str(urls.get("betclic") or ""),
            str(urls.get("unibet") or ""),
            str(urls.get("winamax") or ""),
        ]
    ).lower()
    return text in blob


def discover_anchors(
    *,
    betclic_links: list[Any],
    unibet_events: list[Any],
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
                "betclic_match_id": None,
                "unibet_event_id": None,
                "winamax_match_id": None,
                "fanduel_event_id": None,
            }
        return anchors[key]

    def attach_fr(source: str, home: str, away: str, url: str, **ids: Any) -> None:
        matched = None
        for key, anchor in anchors.items():
            if teams_match(anchor["home_team"], anchor["away_team"], home, away):
                matched = key
                break
        if matched is None:
            anchor = ensure_anchor(home, away)
        else:
            anchor = anchors[matched]
        anchor["sources"].add(source)
        anchor["urls"][source] = url
        for field, value in ids.items():
            if value is not None:
                anchor[field] = value

    for link in betclic_links:
        attach_fr(
            "betclic",
            link.home_team,
            link.away_team,
            link.url,
            betclic_match_id=link.match_id,
        )

    for event in unibet_events:
        attach_fr(
            "unibet",
            event.home_team,
            event.away_team,
            event.url,
            unibet_event_id=event.event_id,
        )

    for link in winamax_links:
        attach_fr(
            "winamax",
            link.home_team,
            link.away_team,
            link.url,
            winamax_match_id=link.match_id,
            winamax_home=link.home_team,
            winamax_away=link.away_team,
            winamax_title=link.title,
            winamax_start=link.start_date,
            winamax_competition=link.competition,
        )

    for event in fanduel_events:
        matched = None
        for key, anchor in anchors.items():
            if teams_match(anchor["home_team"], anchor["away_team"], event.home_team, event.away_team):
                matched = key
                break
        if matched is None:
            continue  # require at least one FR source
        anchor = anchors[matched]
        anchor["sources"].add("fanduel")
        anchor["fanduel_event_id"] = event.event_id
        if getattr(event, "competition_name", ""):
            anchor["competition"] = event.competition_name
            anchor["fanduel_competition"] = event.competition_name
        if getattr(event, "competition_id", ""):
            anchor["fanduel_competition_id"] = event.competition_id

    return [
        a
        for a in anchors.values()
        if "fanduel" in a["sources"] and (a["sources"] & {"betclic", "unibet", "winamax"})
    ]


def build_results_payload(results: list[dict[str, Any]], *, partial: bool = False) -> dict[str, Any]:
    comparables: list[dict[str, Any]] = []
    fr_only: list[dict[str, Any]] = []
    fd_only: list[dict[str, Any]] = []
    progress: list[dict[str, Any]] = []
    for result in results:
        match = result["match"]
        for row in result.get("comparables", []):
            comparables.append({"match": match, **row})
        for row in result.get("fr_only", []):
            fr_only.append({"match": match, **row})
        for row in result.get("fd_only", []):
            fd_only.append({"match": match, **row})
        progress.append(
            {
                "match": match,
                "comparable_count": result.get("comparable_count", 0),
                "fr_only_count": len(result.get("fr_only", [])),
                "fd_only_count": len(result.get("fd_only", [])),
                "fanduel_found": bool(result.get("fanduel_event_id")),
            }
        )
    fr_higher = [row for row in comparables if row.get("best_side") == "fr"]
    return {
        "source": "soccer_player_props_comparable",
        "generated_at": utc_now(),
        "partial": partial,
        "anchors_total": len(results),
        "matches_done": len(results),
        "comparable_count": len(comparables),
        "fr_higher_count": len(fr_higher),
        "fr_only_count": len(fr_only),
        "fd_only_count": len(fd_only),
        "comparables": comparables,
        "fr_higher_comparables": fr_higher,
        "value_comparables": fr_higher,
        "fr_only_comparables": fr_only,
        "fd_only_comparables": fd_only,
        "match_progress": progress,
        "notes": [
            "Familles: buteur, 1er buteur, décisif, passeur, tirs joueur/équipe/match, tirs cadrés, carton, corners.",
            "Books FR: Winamax + Betclic + Unibet. US: FanDuel (toutes compétitions SPORT).",
            "Overlap fort sur buteur; tirs match/équipe et corners surtout US tant que FR ne les ouvre pas.",
        ],
    }


def write_progress_json(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    write_json_atomic(path, payload)


def write_run_status_file(path: Path | None, status: dict[str, Any]) -> None:
    if path is None:
        return
    write_json_atomic(path, status)


def process_anchor(
    anchor: dict[str, Any],
    *,
    betclic: BetclicSoccerClient,
    unibet: UnibetSoccerClient,
    winamax: WinamaxSoccerClient,
    fanduel: FanDuelSoccerClient,
) -> dict[str, Any]:
    book_events: dict[str, dict[str, Any]] = {}
    fr_scraped_at = utc_now()
    if anchor["urls"].get("betclic"):
        try:
            payload = betclic.build_soccer_event_payload(anchor["urls"]["betclic"])
            if payload.get("home_team") and payload.get("away_team"):
                anchor["home_team"] = payload["home_team"]
                anchor["away_team"] = payload["away_team"]
                anchor["match"] = f"{payload['home_team']} vs {payload['away_team']}"
            book_events["betclic"] = payload
        except Exception as exc:
            log.warning("Betclic fail %s: %s", anchor["match"], exc)
    if anchor["urls"].get("unibet"):
        try:
            book_events["unibet"] = unibet.build_soccer_event_payload(anchor["urls"]["unibet"])
        except Exception as exc:
            log.warning("Unibet fail %s: %s", anchor["match"], exc)
    if anchor.get("winamax_match_id"):
        try:
            link = WinamaxSoccerMatchLink(
                match_id=str(anchor["winamax_match_id"]),
                url=str(anchor["urls"].get("winamax") or ""),
                title=str(anchor.get("winamax_title") or anchor["match"]),
                home_team=str(anchor.get("winamax_home") or anchor["home_team"]),
                away_team=str(anchor.get("winamax_away") or anchor["away_team"]),
                start_date=str(anchor.get("winamax_start") or ""),
                competition=str(anchor.get("winamax_competition") or ""),
            )
            book_events["winamax"] = winamax.build_soccer_event_payload(link)
        except Exception as exc:
            log.warning("Winamax fail %s: %s", anchor["match"], exc)

    fd_event = None
    fd_scraped_at = None
    if anchor.get("fanduel_event_id"):
        try:
            fd_event = fanduel.get_event_payload(str(anchor["fanduel_event_id"]))
            fd_scraped_at = utc_now()
        except Exception as exc:
            log.warning("FanDuel fail %s: %s", anchor["match"], exc)

    roster = merge_roster(
        *[roster_from_markets(ev.get("markets") or []) for ev in book_events.values()],
        roster_from_markets((fd_event or {}).get("markets") or []),
    )
    fr_map = build_best_fr_map(
        book_events,
        roster=roster,
        home_team=str(anchor.get("home_team") or ""),
        away_team=str(anchor.get("away_team") or ""),
    )
    fd_map = build_fanduel_map(fd_event, roster=roster, captured_at=fd_scraped_at)
    return assemble_anchor_result(
        anchor,
        book_events=book_events,
        roster=roster,
        fr_map=fr_map,
        fd_map=fd_map,
        fr_scraped_at=fr_scraped_at,
        fd_scraped_at=fd_scraped_at,
        compare_normalized_props=compare_normalized_props,
        enrich_fr_only_row=enrich_fr_only_row,
        enrich_fd_only_row=enrich_fd_only_row,
        attach_capture_times=attach_capture_times,
    )


def run_live_compare(
    *,
    match_filter: str | None = None,
    progress_json: Path | None = None,
    status_json: Path | None = None,
    max_workers: int = 2,
) -> dict[str, Any]:
    write_run_status_file(
        status_json,
        {
            "status": "running",
            "message": "Scan foot FR + FanDuel…",
            "sport": "soccer",
            "match_filter": match_filter or "",
            "updated_at": utc_now(),
            "run_started_at": utc_now(),
        },
    )

    betclic = BetclicSoccerClient()
    unibet = UnibetSoccerClient()
    winamax = WinamaxSoccerClient()
    fanduel = FanDuelSoccerClient()

    with ThreadPoolExecutor(max_workers=4) as pool:
        fut_b = pool.submit(betclic.list_soccer_matches)
        fut_u = pool.submit(unibet.list_soccer_events)
        fut_w = pool.submit(winamax.list_soccer_matches)
        fut_f = pool.submit(fanduel.list_soccer_events)
        betclic_links = fut_b.result()
        unibet_events = fut_u.result()
        winamax_links = fut_w.result()
        fanduel_events = fut_f.result()

    log.info(
        "Listings: betclic=%s unibet=%s winamax=%s fanduel=%s",
        len(betclic_links),
        len(unibet_events),
        len(winamax_links),
        len(fanduel_events),
    )
    anchors = discover_anchors(
        betclic_links=betclic_links,
        unibet_events=unibet_events,
        winamax_links=winamax_links,
        fanduel_events=fanduel_events,
    )
    if match_filter:
        needle = match_filter.lower()
        anchors = [a for a in anchors if anchor_matches_filter(a, needle)]

    # MLS / ligues props d'abord — tirs FanDuel surtout sur MLS aujourd'hui.
    def _anchor_priority(anchor: dict[str, Any]) -> tuple[int, str]:
        blob = " ".join(
            [
                str(anchor.get("match") or ""),
                str(anchor.get("winamax_competition") or ""),
                str(anchor.get("urls", {}).get("betclic") or ""),
            ]
        ).lower()
        if any(k in blob for k in ("mls", "new york city", "inter miami", "la galaxy", "seattle sounders")):
            return (0, blob)
        if any(k in blob for k in ("premier league", "ligue 1", "serie a", "bundesliga", "la liga", "liga mx")):
            return (1, blob)
        return (2, blob)

    anchors = sorted(anchors, key=_anchor_priority)
    log.info("Anchors FR∩US: %s (MLS/props en tete)", len(anchors))
    results: list[dict[str, Any]] = []

    def _handle(anchor: dict[str, Any]) -> dict[str, Any]:
        return process_anchor(
            anchor,
            betclic=betclic,
            unibet=unibet,
            winamax=winamax,
            fanduel=fanduel,
        )

    # 2 workers: moins de saturation VM / tunnel (sinon UI « runner instable »).
    workers = max(1, min(max_workers, 2))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_handle, a): a for a in anchors}
        for fut in as_completed(futs):
            try:
                result = fut.result()
            except Exception as exc:
                anchor = futs[fut]
                log.warning("Anchor fail %s: %s", anchor["match"], exc)
                continue
            results.append(result)
            payload = build_results_payload(results, partial=True)
            write_progress_json(progress_json, payload)
            write_run_status_file(
                status_json,
                {
                    "status": "running",
                    "message": f"Foot {len(results)}/{len(anchors)} — {result['match']}",
                    "sport": "soccer",
                    "match_filter": match_filter or "",
                    "updated_at": utc_now(),
                    "anchors_total": len(anchors),
                    "matches_done": len(results),
                    "comparable_count": payload["comparable_count"],
                    "fr_higher_count": payload["fr_higher_count"],
                },
            )

    payload = build_results_payload(results, partial=False)
    write_progress_json(progress_json, payload)
    write_run_status_file(
        status_json,
        {
            "status": "success",
            "message": f"Foot terminé — {payload['comparable_count']} comparables",
            "sport": "soccer",
            "match_filter": match_filter or "",
            "updated_at": utc_now(),
            "generated_at": payload["generated_at"],
            "anchors_total": payload["anchors_total"],
            "matches_done": payload["matches_done"],
            "comparable_count": payload["comparable_count"],
            "fr_higher_count": payload["fr_higher_count"],
        },
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare soccer props FR vs FanDuel")
    parser.add_argument("--match", default="", help="Filtre match")
    parser.add_argument("-o", "--output", default="", help="JSON output path")
    parser.add_argument("--progress-json", default="", help="Progress JSON path")
    parser.add_argument("--status-json", default="", help="Status JSON path")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = Path(args.output) if args.output else OUTPUT_DIR / "latest_soccer.json"
    progress = Path(args.progress_json) if args.progress_json else output
    status = Path(args.status_json) if args.status_json else OUTPUT_DIR / "run_status_soccer.json"

    payload = run_live_compare(
        match_filter=args.match.strip() or None,
        progress_json=progress,
        status_json=status,
    )
    write_json_atomic(output, payload)
    log.info(
        "Done: comparables=%s fr_higher=%s fr_only=%s fd_only=%s -> %s",
        payload["comparable_count"],
        payload["fr_higher_count"],
        payload["fr_only_count"],
        payload["fd_only_count"],
        output,
    )


if __name__ == "__main__":
    main()
