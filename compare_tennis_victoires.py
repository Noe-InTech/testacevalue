"""Comparaison marches victoire (moneyline / h2h) FR vs FanDuel."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fanduel_client import (
    format_american_moneyline,
    format_french_decimal,
    runner_fanduel_price_bundle,
)
from scan_tennis_aces import BOOK_LABELS
from tennis_books_mapping import normalized_market_to_dict, strip_accents
from tennis_market_mapping import (
    align_fr_outcome_to_fanduel,
    map_fanduel_market_to_compare_key,
)

from compare_tennis_aces_vs_fanduel import (
    BOOK_NORMALIZERS,
    aces_outcome_label_fr,
    collect_fr_higher_rows,
    collect_value_rows,
    compute_paired_value_fields,
    enrich_comparable_row,
)

VICTOIRE_COMPARE_KEY = "h2h"
VICTOIRE_FAMILIES = frozenset({"h2h"})


def is_victoire_market_label(label: str) -> bool:
    lower = strip_accents(label.lower())
    if any(token in lower for token in ("aces", "break", "jeux", "games", "set handicap", "total")):
        if "vainqueur" not in lower and "moneyline" not in lower and "match betting" not in lower:
            return False
    if lower in {"vainqueur du match", "vainqueur", "moneyline", "match betting"}:
        return True
    if lower.startswith("vainqueur"):
        return True
    if "face a face" in lower or "face-a-face" in lower:
        return True
    if "vainqueur du match" in lower:
        return True
    return False


def _align_h2h_outcome(outcome: str, home: str, away: str) -> str:
    if outcome in {"home", "1"}:
        return home
    if outcome in {"away", "2"}:
        return away
    aligned = align_fr_outcome_to_fanduel(outcome, VICTOIRE_COMPARE_KEY, home, away)
    return aligned


def format_ligne_victoires_fr(row: dict[str, Any]) -> str:
    outcome = str(row.get("outcome") or "").strip()
    if outcome:
        return f"Victoire — {outcome}"
    return str(row.get("fr_market_label") or row.get("marche_fr") or "Victoire")


def build_best_fr_victoires_map(
    book_events: dict[str, dict[str, Any]],
    *,
    home: str,
    away: str,
) -> dict[str, dict[str, Any]]:
    if not book_events:
        return {}
    sample = next(iter(book_events.values()))
    home = home or str(sample.get("home_player") or "")
    away = away or str(sample.get("away_player") or "")
    best: dict[str, dict[str, Any]] = {}

    for bookmaker, event in book_events.items():
        normalizer = BOOK_NORMALIZERS.get(bookmaker)
        if not normalizer:
            continue
        for market in event.get("markets") or []:
            label = str(market.get("label") or "").strip()
            if not label or not is_victoire_market_label(label):
                continue
            outcomes = [(str(raw), odds) for raw, odds in (market.get("outcomes") or [])]
            for item in normalizer(label, outcomes, home, away):
                if item.market_family not in VICTOIRE_FAMILIES:
                    continue
                if item.compare_key != VICTOIRE_COMPARE_KEY:
                    continue
                payload = normalized_market_to_dict(item, home, away)
                for outcome, odds in payload["outcomes"].items():
                    if odds is None:
                        continue
                    aligned = _align_h2h_outcome(str(outcome), home, away)
                    if not aligned:
                        continue
                    slot = best.setdefault(
                        VICTOIRE_COMPARE_KEY,
                        {
                            "compare_key": VICTOIRE_COMPARE_KEY,
                            "market_family": "h2h",
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


def build_fanduel_victoires_normalized_map(event: dict[str, Any]) -> dict[str, dict[str, Any]]:
    home = str(event.get("home_player") or "")
    away = str(event.get("away_player") or "")
    variant_map: dict[str, dict[str, Any]] = {}

    for market in event.get("markets") or []:
        label = str(market.get("marketName") or "").strip()
        if not label:
            continue
        compare_key = map_fanduel_market_to_compare_key(market)
        if compare_key != VICTOIRE_COMPARE_KEY:
            continue
        outcomes: dict[str, dict[str, Any]] = {}
        for runner in market.get("runners") or []:
            if runner.get("runnerStatus") not in (None, "ACTIVE"):
                continue
            price_bundle = runner_fanduel_price_bundle(runner)
            if price_bundle.get("decimal_fr") is None:
                continue
            runner_name = str(runner.get("runnerName") or "").strip()
            aligned = _align_h2h_outcome(runner_name, home, away)
            if not aligned:
                continue
            outcomes[aligned] = price_bundle
        if len(outcomes) >= 2:
            variant_map[VICTOIRE_COMPARE_KEY] = {
                "compare_key": VICTOIRE_COMPARE_KEY,
                "market_label": label,
                "outcomes": outcomes,
                "fd_line_source": "h2h",
            }
    return variant_map


def compare_normalized_victoires(
    fr_map: dict[str, dict[str, Any]],
    fd_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    fr_market = fr_map.get(VICTOIRE_COMPARE_KEY)
    fd_market = fd_map.get(VICTOIRE_COMPARE_KEY)
    if not fr_market or not fd_market:
        return rows
    for outcome, fr_payload in fr_market["outcomes"].items():
        fd_bundle = fd_market["outcomes"].get(outcome)
        if not fd_bundle or fd_bundle.get("decimal_fr") is None:
            continue
        rows.append(
            enrich_comparable_row(
                {
                    "compare_key": VICTOIRE_COMPARE_KEY,
                    "market_family": "h2h",
                    "outcome": outcome,
                    "fr_market_label": fr_market["market_label_raw"],
                    "fanduel_market_label": str(fd_market.get("market_label") or "Moneyline"),
                    "fanduel_compare_key": VICTOIRE_COMPARE_KEY,
                    "line_delta": 0.0,
                    "best_fr_odds": float(fr_payload["odds"]),
                    "best_fr_bookmaker": fr_payload["bookmaker_label"],
                    "fanduel_odds": float(fd_bundle.get("decimal_raw") or fd_bundle["decimal_fr"]),
                    "fanduel_american": fd_bundle.get("american"),
                    "fanduel_decimal_fr": float(fd_bundle["decimal_fr"]),
                    **compute_paired_value_fields(
                        outcome=outcome,
                        fr_payload=fr_payload,
                        fr_market=fr_market,
                        fd_market=fd_market,
                    ),
                }
            )
        )
    for row in rows:
        row["ligne_victoires_fr"] = format_ligne_victoires_fr(row)
        row["issue_fr"] = str(row.get("outcome") or "")
    return rows


def collect_fr_only_victoires(
    fr_map: dict[str, dict[str, Any]],
    fd_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    fr_market = fr_map.get(VICTOIRE_COMPARE_KEY)
    if not fr_market:
        return rows
    fd_market = fd_map.get(VICTOIRE_COMPARE_KEY) or {}
    for outcome, fr_payload in fr_market["outcomes"].items():
        if outcome in (fd_market.get("outcomes") or {}):
            continue
        row = {
            "compare_key": VICTOIRE_COMPARE_KEY,
            "market_family": "h2h",
            "outcome": outcome,
            "fr_market_label": fr_market["market_label_raw"],
            "fanduel_market_label": "",
            "best_fr_odds": float(fr_payload["odds"]),
            "best_fr_bookmaker": fr_payload["bookmaker_label"],
            "cote_fr": format_french_decimal(float(fr_payload["odds"])),
            "bookmaker_fr": fr_payload["bookmaker_label"],
            "cote_us_fanduel_ml": "",
            "cote_fr_fanduel": "",
            "ecart_fr_moins_fd": "",
            "meilleur_cote": "FR seul",
            "issue_fr": outcome,
            "marche_fr": fr_market["market_label_raw"],
            "marche_fanduel": "",
        }
        row["ligne_victoires_fr"] = format_ligne_victoires_fr(row)
        rows.append(row)
    return rows


def collect_fd_only_victoires(
    fr_map: dict[str, dict[str, Any]],
    fd_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    fd_market = fd_map.get(VICTOIRE_COMPARE_KEY)
    if not fd_market:
        return rows
    fr_market = fr_map.get(VICTOIRE_COMPARE_KEY) or {}
    for outcome, fd_bundle in (fd_market.get("outcomes") or {}).items():
        if outcome in (fr_market.get("outcomes") or {}):
            continue
        decimal_fr = fd_bundle.get("decimal_fr")
        if decimal_fr is None:
            continue
        row = {
            "compare_key": VICTOIRE_COMPARE_KEY,
            "market_family": "h2h",
            "outcome": outcome,
            "fr_market_label": "",
            "fanduel_market_label": str(fd_market.get("market_label") or "Moneyline"),
            "best_fr_odds": None,
            "best_fr_bookmaker": "",
            "cote_fr": "",
            "bookmaker_fr": "",
            "cote_us_fanduel_ml": format_american_moneyline(fd_bundle.get("american")),
            "cote_fr_fanduel": format_french_decimal(float(decimal_fr)),
            "ecart_fr_moins_fd": "",
            "meilleur_cote": "FanDuel seul",
            "issue_fr": outcome,
            "marche_fr": "",
            "marche_fanduel": str(fd_market.get("market_label") or "Moneyline"),
        }
        row["ligne_victoires_fr"] = format_ligne_victoires_fr(row)
        rows.append(row)
    return rows


def attach_victoires_to_anchor_result(
    compared: dict[str, Any],
    *,
    fanduel_event: dict[str, Any] | None,
    book_events: dict[str, dict[str, Any]],
    home: str,
    away: str,
) -> dict[str, Any]:
    fr_map = build_best_fr_victoires_map(book_events, home=home, away=away) if book_events else {}
    fd_map = build_fanduel_victoires_normalized_map(fanduel_event) if fanduel_event else {}
    comparable = compare_normalized_victoires(fr_map, fd_map)
    fr_only = collect_fr_only_victoires(fr_map, fd_map)
    fd_only = collect_fd_only_victoires(fr_map, fd_map)
    match_name = compared.get("match", "")
    for row in comparable + fr_only + fd_only:
        row["match"] = match_name
    compared["comparable_victoire_count"] = len(comparable)
    compared["comparable_victoires"] = comparable
    compared["fr_only_victoire_count"] = len(fr_only)
    compared["fr_only_victoires"] = fr_only
    compared["fd_only_victoire_count"] = len(fd_only)
    compared["fd_only_victoires"] = fd_only
    compared["fr_victoire_market_count"] = len(fr_map)
    compared["fd_victoire_market_count"] = len(fd_map)
    return compared


def build_victoires_section_payload(
    results: list[dict[str, Any]],
    *,
    partial: bool,
    anchors_total: int | None,
) -> dict[str, Any]:
    comparable_rows: list[dict[str, Any]] = []
    fr_only_rows: list[dict[str, Any]] = []
    fd_only_rows: list[dict[str, Any]] = []
    match_progress: list[dict[str, Any]] = []

    for result in results:
        comparable_rows.extend(result.get("comparable_victoires", []))
        fr_only_rows.extend(result.get("fr_only_victoires", []))
        fd_only_rows.extend(result.get("fd_only_victoires", []))
        match_progress.append(
            {
                "match": result.get("match", ""),
                "comparable_count": int(result.get("comparable_victoire_count", 0)),
                "fr_only_count": int(result.get("fr_only_victoire_count", 0)),
                "fd_only_count": int(result.get("fd_only_victoire_count", 0)),
                "fr_market_count": int(result.get("fr_victoire_market_count", 0)),
                "fd_market_count": int(result.get("fd_victoire_market_count", 0)),
                "fanduel_found": bool(result.get("fanduel_event_id")),
            }
        )

    fr_higher_rows = collect_fr_higher_rows(comparable_rows)
    value_rows = collect_value_rows(comparable_rows, min_ev_percent=0.0)
    fd_events = sum(1 for r in results if int(r.get("fd_victoire_market_count", 0)) > 0)
    fr_events = sum(1 for r in results if int(r.get("fr_victoire_market_count", 0)) > 0)

    return {
        "source": "tennis_victoires_comparable",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "partial": partial,
        "anchors_total": anchors_total if anchors_total is not None else len(match_progress),
        "matches_done": len(match_progress),
        "comparable_count": len(comparable_rows),
        "fr_higher_count": len(fr_higher_rows),
        "value_count": len(value_rows),
        "fr_only_count": len(fr_only_rows),
        "fd_only_count": len(fd_only_rows),
        "fd_event_count": fd_events,
        "fr_event_count": fr_events,
        "comparables": comparable_rows,
        "fr_higher_comparables": fr_higher_rows,
        "value_comparables": value_rows,
        "fr_only_comparables": fr_only_rows,
        "fd_only_comparables": fd_only_rows,
        "match_progress": match_progress,
    }
