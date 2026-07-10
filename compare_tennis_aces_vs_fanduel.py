"""Compare marches aces FR (Unibet/Betclic/Winamax) vs FanDuel."""

from __future__ import annotations

import argparse
import csv
import json
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

from fanduel_client import (
    ACES_EVENT_TABS,
    FanDuelClient,
    format_american_moneyline,
    format_french_decimal,
    runner_decimal_odds,
    runner_fanduel_price_bundle,
)
from scan_tennis_aces import (
    BOOK_LABELS,
    discover_anchor_events,
    find_event_by_players,
    is_aces_market,
    pick_best_quote,
)
from tennis_books_mapping import (
    normalize_betclic_market,
    normalize_unibet_market,
    normalize_winamax_market,
    normalized_market_to_dict,
)
from tennis_market_mapping import (
    align_fr_outcome_to_fanduel,
    fanduel_aces_runner_outcome,
    map_fanduel_aces_market_to_compare_key,
    players_match,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("compare_aces_fanduel")

OUTPUT_DIR = Path(__file__).parent / "output"
BETCLIC_ACES_GRPC = ("ca_ten_ptss",)
COMPARABLE_ACE_PREFIXES = ("aces_total|", "aces_player|")
BOOK_NORMALIZERS = {
    "unibet": normalize_unibet_market,
    "betclic": normalize_betclic_market,
    "winamax": normalize_winamax_market,
}
ACE_FAMILIES = {"aces_total", "aces_player", "aces_h2h"}
COMPARABLE_CSV_FIELDS = [
    "match",
    "issue_fr",
    "marche_fr",
    "marche_fanduel",
    "cote_fr",
    "bookmaker_fr",
    "cote_us_fanduel_ml",
    "cote_fr_fanduel",
    "ecart_fr_moins_fd",
    "meilleur_cote",
]


def aces_outcome_label_fr(outcome: str) -> str:
    mapping = {
        "Over": "Plus",
        "Under": "Moins",
        "over": "Plus",
        "under": "Moins",
    }
    return mapping.get(outcome, outcome)


def enrich_comparable_row(row: dict[str, Any]) -> dict[str, Any]:
    fr_odds_fr = round(float(row["best_fr_odds"]), 2)
    fd_decimal_fr = float(row["fanduel_decimal_fr"])
    fd_american = row.get("fanduel_american")
    price_delta = round(fr_odds_fr - fd_decimal_fr, 2)
    if price_delta > 0:
        best_side = "fr"
    elif price_delta < 0:
        best_side = "fanduel"
    else:
        best_side = "tie"
    enriched = {
        **row,
        "outcome_fr": aces_outcome_label_fr(str(row.get("outcome", ""))),
        "best_fr_odds": fr_odds_fr,
        "best_fr_odds_fr": format_french_decimal(fr_odds_fr),
        "fanduel_american": fd_american,
        "fanduel_moneyline_us": format_american_moneyline(fd_american),
        "fanduel_decimal_fr": fd_decimal_fr,
        "fanduel_decimal_fr_display": format_french_decimal(fd_decimal_fr),
        "price_delta": price_delta,
        "best_side": best_side,
        "cote_fr": format_french_decimal(fr_odds_fr),
        "bookmaker_fr": row.get("best_fr_bookmaker", ""),
        "cote_us_fanduel_ml": format_american_moneyline(fd_american),
        "cote_fr_fanduel": format_french_decimal(fd_decimal_fr),
        "ecart_fr_moins_fd": f"{price_delta:+.2f}".replace(".", ","),
        "meilleur_cote": "FR" if best_side == "fr" else "FanDuel" if best_side == "fanduel" else "Egalite",
        "issue_fr": aces_outcome_label_fr(str(row.get("outcome", ""))),
        "marche_fr": row.get("fr_market_label", ""),
        "marche_fanduel": row.get("fanduel_market_label", ""),
    }
    return enriched


def has_comparable_fr_aces(fr_map: dict[str, dict[str, Any]]) -> bool:
    return any(key.startswith(COMPARABLE_ACE_PREFIXES) for key in fr_map)


def build_best_fr_normalized_map_from_quotes(
    quotes: list[dict[str, Any]],
    *,
    home: str,
    away: str,
) -> dict[str, dict[str, Any]]:
    grouped: dict[tuple[str, str], list[tuple[str, float | None]]] = defaultdict(list)
    for quote in quotes:
        bookmaker = str(quote.get("bookmaker", "")).strip()
        label = str(quote.get("market_label", "")).strip()
        if not bookmaker or not label:
            continue
        grouped[(bookmaker, label)].append(
            (str(quote.get("outcome_label", "")), quote.get("odds"))
        )

    best: dict[str, dict[str, Any]] = {}
    for (bookmaker, label), outcomes in grouped.items():
        normalizer = BOOK_NORMALIZERS.get(bookmaker)
        if not normalizer:
            continue
        for item in normalizer(label, outcomes, home, away):
            if item.market_family not in ACE_FAMILIES:
                continue
            payload = normalized_market_to_dict(item, home, away)
            for outcome, odds in payload["outcomes"].items():
                aligned = align_fr_outcome_to_fanduel(
                    outcome,
                    item.compare_key,
                    home,
                    away,
                )
                slot = best.setdefault(
                    item.compare_key,
                    {
                        "compare_key": item.compare_key,
                        "market_family": item.market_family,
                        "market_label_raw": item.market_label_raw,
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


def anchor_matches_filter(anchor: dict[str, Any], match_filter: str) -> bool:
    needle = match_filter.strip().lower()
    if not needle:
        return True
    haystack = " ".join(
        [
            str(anchor.get("home_player", "")),
            str(anchor.get("away_player", "")),
            str(anchor.get("competition", "")),
        ]
    ).lower()
    return needle in haystack


def _fetch_betclic_aces_event(betclic: Any, url: str) -> dict[str, Any]:
    return betclic.build_event_payload(url, grpc_categories=BETCLIC_ACES_GRPC)


def _discover_fanduel_singles(fanduel: FanDuelClient) -> list[Any]:
    page_ids = fanduel.discover_tennis_page_ids(
        ("wimbledon", "wimbledon-simples-hommes", "wimbledon-simples-dames")
    )
    return [event for event in fanduel.list_tennis_events(page_ids) if not event.is_doubles]


def fetch_live_aces_book_data(
    *,
    match_filter: str = "",
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    list[Any],
    list[Any],
]:
    from betclic_client import BetclicClient
    from unibet_client import UnibetClient
    from winamax_client import WinamaxClient

    unibet = UnibetClient()
    betclic = BetclicClient()
    winamax = WinamaxClient()
    fanduel = FanDuelClient()

    with ThreadPoolExecutor(max_workers=4) as pool:
        fut_unibet_meta = pool.submit(unibet.list_singles_tennis_events)
        fut_betclic_links = pool.submit(betclic.list_tennis_match_links)
        fut_winamax_links = pool.submit(winamax.list_singles_tennis_matches)
        fut_fanduel_list = pool.submit(_discover_fanduel_singles, fanduel)

        def _safe_future_result(future: Any, label: str, fallback: Any) -> Any:
            try:
                return future.result()
            except Exception as exc:
                log.warning("%s indisponible (live): %s", label, exc)
                return fallback

        unibet_meta = _safe_future_result(fut_unibet_meta, "Unibet", [])
        betclic_links = _safe_future_result(fut_betclic_links, "Betclic", [])
        winamax_links = _safe_future_result(fut_winamax_links, "Winamax", [])
        fanduel_event_list = _safe_future_result(fut_fanduel_list, "FanDuel", [])

    betclic_events: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(betclic_links)))) as pool:
        futures = {
            pool.submit(_fetch_betclic_aces_event, betclic, link.url): link
            for link in betclic_links
        }
        for future in as_completed(futures):
            link = futures[future]
            try:
                betclic_events.append(future.result())
            except Exception as exc:
                log.warning("Betclic ignore %s: %s", link.url, exc)

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
        event["match_id"]: event
        for event in winamax.build_event_payloads(winamax_links)
    }

    anchors = discover_anchor_events(unibet_meta, betclic_events, winamax_links)
    if match_filter:
        anchors = [anchor for anchor in anchors if anchor_matches_filter(anchor, match_filter)]

    log.info(
        "%d match(s) ancres | %d FanDuel | Betclic gRPC=%s",
        len(anchors),
        len(fanduel_event_list),
        ",".join(BETCLIC_ACES_GRPC),
    )
    return (
        anchors,
        unibet_payloads,
        betclic_events,
        winamax_payloads,
        fanduel_event_list,
        winamax_links,
    )


def assemble_book_events(
    anchor: dict[str, Any],
    *,
    unibet_payloads: list[dict[str, Any]],
    betclic_events: list[dict[str, Any]],
    winamax_links: list[Any],
    winamax_payloads: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
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
    return book_events


def extract_fanduel_ace_quotes(event: dict[str, Any]) -> list[dict[str, Any]]:
    home = event.get("home_player", "")
    away = event.get("away_player", "")
    rows: list[dict[str, Any]] = []
    for market in event.get("markets", []):
        label = str(market.get("marketName", "")).strip()
        if not label or not is_aces_market(label):
            continue
        compare_key = map_fanduel_aces_market_to_compare_key(market, home, away)
        for runner in market.get("runners", []):
            if runner.get("runnerStatus") not in (None, "ACTIVE"):
                continue
            odds = runner_decimal_odds(runner)
            if odds is None:
                continue
            runner_name = str(runner.get("runnerName", "")).strip()
            price_bundle = runner_fanduel_price_bundle(runner)
            rows.append(
                {
                    "bookmaker": "fanduel",
                    "bookmaker_label": "FanDuel",
                    "market_label": label,
                    "outcome_label": runner_name,
                    "aligned_outcome": fanduel_aces_runner_outcome(market, runner_name, compare_key),
                    "compare_key": compare_key or "",
                    "odds": float(odds),
                    "american": price_bundle.get("american"),
                    "decimal_fr": price_bundle.get("decimal_fr"),
                }
            )
    return rows


def build_best_fr_normalized_map(
    book_events: dict[str, dict[str, Any]],
    *,
    home: str = "",
    away: str = "",
) -> dict[str, dict[str, Any]]:
    if not book_events:
        return {}
    sample = next(iter(book_events.values()))
    home = home or sample.get("home_player", "")
    away = away or sample.get("away_player", "")
    best: dict[str, dict[str, Any]] = {}

    for bookmaker, event in book_events.items():
        normalizer = BOOK_NORMALIZERS[bookmaker]
        for market in event.get("markets", []):
            label = str(market.get("label", "")).strip()
            if not is_aces_market(label):
                continue
            outcomes = [(str(raw), odds) for raw, odds in market.get("outcomes", [])]
            for item in normalizer(label, outcomes, home, away):
                if item.market_family not in ACE_FAMILIES:
                    continue
                payload = normalized_market_to_dict(item, home, away)
                for outcome, odds in payload["outcomes"].items():
                    aligned = align_fr_outcome_to_fanduel(
                        outcome,
                        item.compare_key,
                        home,
                        away,
                    )
                    slot = best.setdefault(
                        item.compare_key,
                        {
                            "compare_key": item.compare_key,
                            "market_family": item.market_family,
                            "market_label_raw": item.market_label_raw,
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


def build_fanduel_normalized_map(event: dict[str, Any]) -> dict[str, dict[str, Any]]:
    home = event.get("home_player", "")
    away = event.get("away_player", "")
    variant_map: dict[str, dict[str, Any]] = {}

    for market in event.get("markets", []):
        label = str(market.get("marketName", "")).strip()
        if not is_aces_market(label):
            continue
        compare_key = map_fanduel_aces_market_to_compare_key(market, home, away)
        if not compare_key or not compare_key.startswith(("aces_total|", "aces_player|")):
            continue
        outcomes: dict[str, dict[str, Any]] = {}
        for runner in market.get("runners", []):
            if runner.get("runnerStatus") not in (None, "ACTIVE"):
                continue
            price_bundle = runner_fanduel_price_bundle(runner)
            if price_bundle.get("decimal_fr") is None:
                continue
            runner_name = str(runner.get("runnerName", "")).strip()
            aligned = fanduel_aces_runner_outcome(market, runner_name, compare_key)
            outcomes[aligned] = price_bundle
        if outcomes:
            variant_map[compare_key] = {
                "compare_key": compare_key,
                "market_label": label,
                "outcomes": outcomes,
            }
    return variant_map


def compare_normalized_aces(
    fr_map: dict[str, dict[str, Any]],
    fd_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for compare_key, fr_market in fr_map.items():
        fd_market = fd_map.get(compare_key)
        if not fd_market:
            continue
        for outcome, fr_payload in fr_market["outcomes"].items():
            fd_bundle = fd_market["outcomes"].get(outcome)
            if not fd_bundle or fd_bundle.get("decimal_fr") is None:
                continue
            fr_odds = float(fr_payload["odds"])
            rows.append(
                enrich_comparable_row(
                    {
                        "compare_key": compare_key,
                        "market_family": fr_market["market_family"],
                        "outcome": outcome,
                        "fr_market_label": fr_market["market_label_raw"],
                        "fanduel_market_label": fd_market["market_label"],
                        "best_fr_odds": fr_odds,
                        "best_fr_bookmaker": fr_payload["bookmaker_label"],
                        "fanduel_odds": float(fd_bundle.get("decimal_raw") or fd_bundle["decimal_fr"]),
                        "fanduel_american": fd_bundle.get("american"),
                        "fanduel_decimal_fr": float(fd_bundle["decimal_fr"]),
                    }
                )
            )
    return rows


def compare_match_to_fanduel(
    match_meta: dict[str, Any],
    fanduel_event: dict[str, Any] | None,
    book_events: dict[str, dict[str, Any]],
    *,
    fr_map: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    home = match_meta.get("home_player", "")
    away = match_meta.get("away_player", "")
    fd_quotes = extract_fanduel_ace_quotes(fanduel_event) if fanduel_event else []
    fd_best = pick_best_quote(fd_quotes)
    fr_best = match_meta.get("best_overall")
    if fr_map is None:
        fr_map = build_best_fr_normalized_map(book_events, home=home, away=away)
    fd_map = build_fanduel_normalized_map(fanduel_event) if fanduel_event else {}
    comparable = compare_normalized_aces(fr_map, fd_map)
    for row in comparable:
        row["match"] = match_meta["match"]
    fr_higher = [row for row in comparable if row["best_side"] == "fr"]

    raw_delta = None
    raw_best_side = None
    if fr_best and fd_best and fr_best.get("odds") is not None and fd_best.get("odds") is not None:
        raw_delta = float(fr_best["odds"]) - float(fd_best["odds"])
        raw_best_side = "fr" if raw_delta > 0 else "fanduel" if raw_delta < 0 else "tie"

    return {
        "match": match_meta["match"],
        "home_player": home,
        "away_player": away,
        "competition": match_meta.get("competition", ""),
        "sources": match_meta.get("sources", []),
        "urls": match_meta.get("urls", {}),
        "fanduel_event_id": (fanduel_event or {}).get("event_id", ""),
        "fanduel_ace_quote_count": len(fd_quotes),
        "fanduel_quotes": fd_quotes,
        "fanduel_best_overall": fd_best,
        "comparable_ace_count": len(comparable),
        "fr_higher_than_fanduel_count": len(fr_higher),
        "comparable_aces": comparable,
        "raw_best_fr_vs_fanduel": {
            "best_fr": fr_best,
            "best_fanduel": fd_best,
            "price_delta": raw_delta,
            "best_side": raw_best_side,
            "note": "Comparaison brute: marches aces potentiellement differents.",
        },
    }


def collect_comparable_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        for row in result.get("comparable_aces", []):
            rows.append({"match": result["match"], **row})
    return rows


def collect_fr_higher_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("best_side") == "fr"]


def comparable_row_to_csv(row: dict[str, Any]) -> dict[str, str]:
    return {
        "match": str(row.get("match", "")),
        "issue_fr": str(row.get("issue_fr", "")),
        "marche_fr": str(row.get("marche_fr", "")),
        "marche_fanduel": str(row.get("marche_fanduel", "")),
        "cote_fr": str(row.get("cote_fr", "")),
        "bookmaker_fr": str(row.get("bookmaker_fr", "")),
        "cote_us_fanduel_ml": str(row.get("cote_us_fanduel_ml", "")),
        "cote_fr_fanduel": str(row.get("cote_fr_fanduel", "")),
        "ecart_fr_moins_fd": str(row.get("ecart_fr_moins_fd", "")),
        "meilleur_cote": str(row.get("meilleur_cote", "")),
    }


def write_comparable_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fr_higher_rows = collect_fr_higher_rows(rows)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMPARABLE_CSV_FIELDS)
        writer.writerow({"match": "SECTION", "issue_fr": "Toutes les cotes comparables"})
        writer.writeheader()
        for row in rows:
            writer.writerow(comparable_row_to_csv(row))
        writer.writerow({})
        writer.writerow(
            {"match": "SECTION", "issue_fr": "Cotes FR superieures a FanDuel"}
        )
        writer.writeheader()
        if fr_higher_rows:
            for row in fr_higher_rows:
                writer.writerow(comparable_row_to_csv(row))
        else:
            writer.writerow(
                {
                    "match": "",
                    "issue_fr": "Aucune cote FR superieure a FanDuel sur ce run.",
                }
            )


def write_comparable_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    fr_higher_rows = collect_fr_higher_rows(rows)
    lines = [
        "# Comparatif aces tennis FR vs FanDuel",
        "",
        f"Nombre de cotes comparables : **{len(rows)}**",
        "",
        "## 1. Toutes les cotes comparables",
        "",
        "| Match | Issue | Marche FR | Marche FanDuel | Cote FR | Book FR | ML US FanDuel | Cote FR FanDuel | Ecart | Meilleur |",
        "| --- | --- | --- | --- | ---: | --- | ---: | ---: | ---: | --- |",
    ]
    if not rows:
        lines.append("| *(aucune)* | | | | | | | | | |")
    for row in rows:
        lines.append(
            f"| {row.get('match', '')} | {row.get('issue_fr', '')} | "
            f"{row.get('marche_fr', '')} | {row.get('marche_fanduel', '')} | "
            f"{row.get('cote_fr', '')} | {row.get('bookmaker_fr', '')} | "
            f"{row.get('cote_us_fanduel_ml', '')} | {row.get('cote_fr_fanduel', '')} | "
            f"{row.get('ecart_fr_moins_fd', '')} | {row.get('meilleur_cote', '')} |"
        )
    lines.extend(
        [
            "",
            "## 2. Cotes FR superieures a FanDuel",
            "",
            "| Match | Issue | Marche FR | Marche FanDuel | Cote FR | Book FR | ML US FanDuel | Cote FR FanDuel | Ecart |",
            "| --- | --- | --- | --- | ---: | --- | ---: | ---: | ---: |",
        ]
    )
    if not fr_higher_rows:
        lines.append("| *(aucune)* | | | | | | | | |")
    for row in fr_higher_rows:
        lines.append(
            f"| {row.get('match', '')} | {row.get('issue_fr', '')} | "
            f"{row.get('marche_fr', '')} | {row.get('marche_fanduel', '')} | "
            f"{row.get('cote_fr', '')} | {row.get('bookmaker_fr', '')} | "
            f"{row.get('cote_us_fanduel_ml', '')} | {row.get('cote_fr_fanduel', '')} | "
            f"{row.get('ecart_fr_moins_fd', '')} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _export_results(results: list[dict[str, Any]], output: Path | None) -> Path:
    comparable_rows = collect_comparable_rows(results)
    fr_higher_rows = collect_fr_higher_rows(comparable_rows)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = output or OUTPUT_DIR / f"tennis_aces_comparable_{stamp}.csv"
    json_path = csv_path.with_suffix(".json")
    md_path = csv_path.with_suffix(".md")

    payload = {
        "source": "tennis_aces_comparable",
        "generated_at": datetime.now().isoformat(),
        "comparable_count": len(comparable_rows),
        "fr_higher_count": len(fr_higher_rows),
        "comparables": comparable_rows,
        "fr_higher_comparables": fr_higher_rows,
    }
    write_comparable_csv(csv_path, comparable_rows)
    write_comparable_markdown(md_path, comparable_rows)
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    log.info("%d cote(s) comparable(s)", len(comparable_rows))
    log.info("%d cote(s) FR > FanDuel", len(fr_higher_rows))
    log.info("Export CSV : %s", csv_path)
    log.info("Export MD  : %s", md_path)
    log.info("Export JSON : %s", json_path)
    return csv_path


def find_fanduel_event(
    home: str,
    away: str,
    fanduel_events: list[Any],
) -> Any | None:
    for event in fanduel_events:
        if players_match(home, event.home_player) and players_match(away, event.away_player):
            return event
        if players_match(home, event.away_player) and players_match(away, event.home_player):
            return event
    return None


def _compare_anchors(
    anchors: list[dict[str, Any]],
    *,
    unibet_payloads: list[dict[str, Any]],
    betclic_events: list[dict[str, Any]],
    winamax_links: list[Any],
    winamax_payloads: dict[str, dict[str, Any]],
    fanduel_event_list: list[Any],
    match_meta_by_key: dict[str, dict[str, Any]] | None = None,
    fr_map_by_key: dict[str, dict[str, dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    fanduel = FanDuelClient()
    pending: list[tuple[dict[str, Any], dict[str, dict[str, Any]], Any, dict[str, dict[str, Any]] | None]] = []
    results: list[dict[str, Any]] = []

    for anchor in anchors:
        home = anchor["home_player"]
        away = anchor["away_player"]
        match_key = f"{home} vs {away}"
        match_meta = (match_meta_by_key or {}).get(match_key) or {
            "match": match_key,
            "home_player": home,
            "away_player": away,
            "competition": anchor.get("competition", ""),
            "sources": anchor.get("sources", []),
            "urls": anchor.get("urls", {}),
            "best_overall": None,
        }
        book_events = assemble_book_events(
            anchor,
            unibet_payloads=unibet_payloads,
            betclic_events=betclic_events,
            winamax_links=winamax_links,
            winamax_payloads=winamax_payloads,
        )
        if not book_events and not (fr_map_by_key or {}).get(match_key):
            continue

        fr_map = (fr_map_by_key or {}).get(match_key)
        if fr_map is None and book_events:
            fr_map = build_best_fr_normalized_map(book_events, home=home, away=away)
        elif fr_map is None:
            fr_map = {}

        if not has_comparable_fr_aces(fr_map):
            compared = compare_match_to_fanduel(
                match_meta,
                None,
                book_events,
                fr_map=fr_map,
            )
            results.append(compared)
            log.info("%s | 0 comparable(s) (pas d'aces O/U FR alignables)", compared["match"])
            continue

        fanduel_meta = find_fanduel_event(home, away, fanduel_event_list)
        if not fanduel_meta:
            compared = compare_match_to_fanduel(
                match_meta,
                None,
                book_events,
                fr_map=fr_map,
            )
            results.append(compared)
            log.info("%s | 0 comparable(s) (FanDuel introuvable)", compared["match"])
            continue
        pending.append((match_meta, book_events, fanduel_meta, fr_map))

    if pending:
        with ThreadPoolExecutor(max_workers=min(4, len(pending))) as pool:
            futures = {
                pool.submit(
                    fanduel.build_event_payload,
                    fanduel_meta,
                    tabs=ACES_EVENT_TABS,
                ): (match_meta, book_events, fanduel_meta, fr_map)
                for match_meta, book_events, fanduel_meta, fr_map in pending
            }
            for future in as_completed(futures):
                match_meta, book_events, fanduel_meta, fr_map = futures[future]
                try:
                    fanduel_event = future.result()
                except Exception as exc:
                    log.warning("FanDuel ignore %s: %s", fanduel_meta.name, exc)
                    fanduel_event = None
                compared = compare_match_to_fanduel(
                    match_meta,
                    fanduel_event,
                    book_events,
                    fr_map=fr_map,
                )
                results.append(compared)
                log.info(
                    "%s | %d comparable(s)",
                    compared["match"],
                    compared["comparable_ace_count"],
                )
    return results


def run_live_compare(output: Path | None = None, *, match_filter: str = "") -> Path:
    (
        anchors,
        unibet_payloads,
        betclic_events,
        winamax_payloads,
        fanduel_event_list,
        winamax_links,
    ) = fetch_live_aces_book_data(match_filter=match_filter)
    results = _compare_anchors(
        anchors,
        unibet_payloads=unibet_payloads,
        betclic_events=betclic_events,
        winamax_links=winamax_links,
        winamax_payloads=winamax_payloads,
        fanduel_event_list=fanduel_event_list,
    )
    return _export_results(results, output)


def run_from_scan_json(
    scan_json: Path,
    output: Path | None = None,
    *,
    match_filter: str = "",
) -> Path:
    scan_payload = json.loads(scan_json.read_text(encoding="utf-8"))
    fanduel = FanDuelClient()
    fanduel_event_list = _discover_fanduel_singles(fanduel)

    scan_results = scan_payload.get("results", [])
    if match_filter:
        scan_results = [
            result
            for result in scan_results
            if anchor_matches_filter(
                {
                    "home_player": result.get("home_player", ""),
                    "away_player": result.get("away_player", ""),
                    "competition": result.get("competition", ""),
                },
                match_filter,
            )
        ]

    match_meta_by_key: dict[str, dict[str, Any]] = {}
    fr_map_by_key: dict[str, dict[str, dict[str, Any]]] = {}
    anchors: list[dict[str, Any]] = []
    for scan_result in scan_results:
        home = scan_result.get("home_player", "")
        away = scan_result.get("away_player", "")
        match_key = scan_result.get("match") or f"{home} vs {away}"
        match_meta_by_key[match_key] = scan_result
        fr_map_by_key[match_key] = build_best_fr_normalized_map_from_quotes(
            scan_result.get("quotes", []),
            home=home,
            away=away,
        )
        anchors.append(
            {
                "home_player": home,
                "away_player": away,
                "competition": scan_result.get("competition", ""),
                "sources": scan_result.get("sources", []),
                "urls": scan_result.get("urls", {}),
            }
        )

    log.info(
        "Mode scan-json: %d match(s), pas de re-scrape FR",
        len(anchors),
    )
    results = _compare_anchors(
        anchors,
        unibet_payloads=[],
        betclic_events=[],
        winamax_links=[],
        winamax_payloads={},
        fanduel_event_list=fanduel_event_list,
        match_meta_by_key=match_meta_by_key,
        fr_map_by_key=fr_map_by_key,
    )
    return _export_results(results, output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare aces FR vs FanDuel")
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument(
        "--scan-json",
        type=Path,
        help="Reutiliser un export scan_tennis_aces.json (sinon scan live complet)",
    )
    parser.add_argument(
        "--match",
        metavar="TEXT",
        help="Filtrer un match (ex: fery, sinner)",
    )
    args = parser.parse_args()
    if args.scan_json:
        run_from_scan_json(args.scan_json, args.output, match_filter=args.match or "")
    else:
        run_live_compare(args.output, match_filter=args.match or "")
