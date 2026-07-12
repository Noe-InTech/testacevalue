"""Comparaison marches breaks / tie-break FR vs FanDuel."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from fanduel_client import (
    format_american_moneyline,
    format_french_decimal,
    runner_fanduel_price_bundle,
)
from scan_tennis_aces import BOOK_LABELS, is_breaks_market
from tennis_books_mapping import (
    normalized_market_to_dict,
    strip_accents,
)
from tennis_market_mapping import (
    align_fr_outcome_to_fanduel,
    fanduel_breaks_runner_outcome,
    format_numeric_line,
    map_fanduel_breaks_market_to_compare_key,
    players_match,
)

from compare_tennis_aces_vs_fanduel import (
    BOOK_NORMALIZERS,
    aces_outcome_label_fr,
    collect_fr_higher_rows,
    collect_value_rows,
    compute_paired_value_fields,
    enrich_comparable_row,
)

COMPARABLE_BREAK_PREFIXES = (
    "breaks_total|",
    "breaks_player|",
    "tie_break_match|",
    "tie_break_set|",
)
COMPARABLE_BREAK_EXACT_KEYS = frozenset({"first_break"})
BREAK_FAMILIES = frozenset(
    {"breaks_total", "breaks_player", "tie_break_match", "tie_break_set", "first_break"}
)


def is_comparable_break_key(compare_key: str) -> bool:
    if compare_key in COMPARABLE_BREAK_EXACT_KEYS:
        return True
    return compare_key.startswith(COMPARABLE_BREAK_PREFIXES)


def _parse_break_line_key(compare_key: str) -> tuple[str, str, float | None]:
    parts = compare_key.split("|")
    family = parts[0] if parts else ""
    if family == "breaks_total" and len(parts) >= 2:
        try:
            return family, "", float(parts[1])
        except ValueError:
            return family, "", None
    if family == "breaks_player" and len(parts) >= 3:
        try:
            return family, parts[1], float(parts[2])
        except ValueError:
            return family, parts[1], None
    if family == "tie_break_match" and len(parts) >= 2:
        try:
            return family, "", float(parts[1])
        except ValueError:
            return family, "", None
    if family == "tie_break_set" and len(parts) >= 2:
        return family, parts[1], None
    return family, "", None


def _break_player_token_match(token_a: str, token_b: str) -> bool:
    if token_a == token_b:
        return True
    if players_match(token_a.replace("_", " "), token_b.replace("_", " ")):
        return True
    if len(token_a) >= 4 and len(token_b) >= 4 and (
        token_a.startswith(token_b) or token_b.startswith(token_a)
    ):
        return True
    return False


def _find_break_market_near_line(
    fr_compare_key: str,
    fd_map: dict[str, dict[str, Any]],
    *,
    max_delta: float = 2.0,
) -> tuple[str | None, dict[str, Any] | None, float | None]:
    exact = fd_map.get(fr_compare_key)
    if exact:
        return fr_compare_key, exact, 0.0

    family, token, line = _parse_break_line_key(fr_compare_key)
    if line is None and family not in {"tie_break_set"}:
        return None, None, None

    best_key: str | None = None
    best_market: dict[str, Any] | None = None
    best_delta: float | None = None
    for fd_key, fd_market in fd_map.items():
        fd_family, fd_token, fd_line = _parse_break_line_key(fd_key)
        if fd_family != family:
            continue
        if family == "tie_break_set":
            if fd_token == token:
                return fd_key, fd_market, 0.0
            continue
        if fd_line is None or line is None:
            continue
        if family == "breaks_player" and not _break_player_token_match(token, fd_token):
            continue
        delta = abs(fd_line - line)
        if delta > max_delta:
            continue
        if best_delta is None or delta < best_delta:
            best_key = fd_key
            best_market = fd_market
            best_delta = delta
    return best_key, best_market, best_delta


def _skip_fr_break_market_label(label_lower: str) -> bool:
    lower = strip_accents(label_lower)
    if any(token in lower for token in (" jeu", "face a face", "face-a-face", "break points")):
        return True
    if "balle de break" in lower and "plus / moins" not in lower:
        return True
    return False


def format_ligne_breaks_fr(row: dict[str, Any]) -> str:
    issue = aces_outcome_label_fr(str(row.get("outcome", "")))
    compare_key = str(row.get("compare_key", ""))
    parts = compare_key.split("|")
    family = parts[0] if parts else ""

    if family == "breaks_player" and len(parts) >= 3:
        player = parts[1].replace("_", " ").title()
        line = parts[2].replace(".", ",")
        return f"{issue} de {line} breaks — {player}"
    if family == "breaks_total" and len(parts) >= 2:
        line = parts[1].replace(".", ",")
        return f"{issue} de {line} breaks — match"
    if family == "tie_break_match" and len(parts) >= 2:
        line = parts[1].replace(".", ",")
        return f"{issue} de {line} tie-break(s) — match"
    if family == "tie_break_set" and len(parts) >= 2:
        return f"{issue} — tie-break set {parts[1]}"
    if family == "first_break":
        player = str(row.get("outcome", "")).strip()
        return f"Premier break — {player}" if player else "Premier break"

    marche = str(row.get("fr_market_label") or row.get("marche_fr", "")).strip()
    if marche and issue:
        return f"{issue} — {marche}"
    return marche or issue or compare_key


def build_best_fr_breaks_map(
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
            if not is_breaks_market(label):
                continue
            outcomes = [(str(raw), odds) for raw, odds in market.get("outcomes", [])]
            for item in normalizer(label, outcomes, home, away):
                if item.market_family not in BREAK_FAMILIES:
                    continue
                if _skip_fr_break_market_label(label.lower()):
                    continue
                payload = normalized_market_to_dict(item, home, away)
                for outcome, odds in payload["outcomes"].items():
                    aligned = align_fr_outcome_to_fanduel(
                        outcome, item.compare_key, home, away
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


def _tier_break_runner_to_over_line(runner_name: str) -> str | None:
    match = re.match(r"(\d+)\+", runner_name.strip().lower())
    if not match:
        return None
    return format_numeric_line(int(match.group(1)) - 0.5)


def _tier_break_key_to_ou_key(compare_key: str, line: str) -> str | None:
    if compare_key == "breaks_total_tiers":
        return f"breaks_total|{line}"
    if compare_key.startswith("breaks_player_tiers|"):
        token = compare_key.split("|", 1)[1]
        return f"breaks_player|{token}|{line}"
    return None


def _fanduel_break_display_label(fd_market: dict[str, Any], outcome: str) -> str:
    base = str(fd_market.get("market_label", ""))
    bundle = fd_market.get("outcomes", {}).get(outcome, {})
    tier_runner = bundle.get("fd_tier_runner")
    if tier_runner:
        return f"{base} — {tier_runner} (tier)"
    return base


def build_fanduel_breaks_normalized_map(event: dict[str, Any]) -> dict[str, dict[str, Any]]:
    home = event.get("home_player", "")
    away = event.get("away_player", "")
    variant_map: dict[str, dict[str, Any]] = {}

    for market in event.get("markets", []):
        label = str(market.get("marketName", "")).strip()
        if not label or not is_breaks_market(label):
            continue
        compare_key = map_fanduel_breaks_market_to_compare_key(market, home, away)
        if not compare_key:
            continue

        if compare_key == "first_break":
            outcomes: dict[str, dict[str, Any]] = {}
            for runner in market.get("runners", []):
                if runner.get("runnerStatus") not in (None, "ACTIVE"):
                    continue
                price_bundle = runner_fanduel_price_bundle(runner)
                if price_bundle.get("decimal_fr") is None:
                    continue
                runner_name = str(runner.get("runnerName", "")).strip()
                aligned = align_fr_outcome_to_fanduel(
                    runner_name, compare_key, home, away
                )
                outcomes[aligned] = price_bundle
            if outcomes:
                variant_map[compare_key] = {
                    "compare_key": compare_key,
                    "market_label": label,
                    "outcomes": outcomes,
                    "fd_line_source": "player",
                }
            continue

        if compare_key.startswith("tie_break_set|"):
            outcomes = {}
            for runner in market.get("runners", []):
                if runner.get("runnerStatus") not in (None, "ACTIVE"):
                    continue
                price_bundle = runner_fanduel_price_bundle(runner)
                if price_bundle.get("decimal_fr") is None:
                    continue
                runner_name = str(runner.get("runnerName", "")).strip()
                aligned = fanduel_breaks_runner_outcome(market, runner_name, compare_key)
                outcomes[aligned] = price_bundle
            if outcomes:
                variant_map[compare_key] = {
                    "compare_key": compare_key,
                    "market_label": label,
                    "outcomes": outcomes,
                    "fd_line_source": "yes_no",
                }
            continue

        if compare_key.startswith(("breaks_total|", "breaks_player|", "tie_break_match|")):
            outcomes: dict[str, dict[str, Any]] = {}
            for runner in market.get("runners", []):
                if runner.get("runnerStatus") not in (None, "ACTIVE"):
                    continue
                price_bundle = runner_fanduel_price_bundle(runner)
                if price_bundle.get("decimal_fr") is None:
                    continue
                runner_name = str(runner.get("runnerName", "")).strip()
                aligned = fanduel_breaks_runner_outcome(market, runner_name, compare_key)
                outcomes[aligned] = price_bundle
            if outcomes:
                variant_map[compare_key] = {
                    "compare_key": compare_key,
                    "market_label": label,
                    "outcomes": outcomes,
                    "fd_line_source": "ou",
                }
            continue

        if compare_key not in {"breaks_total_tiers"} and not compare_key.startswith(
            "breaks_player_tiers|"
        ):
            continue

        for runner in market.get("runners", []):
            if runner.get("runnerStatus") not in (None, "ACTIVE"):
                continue
            runner_name = str(runner.get("runnerName", "")).strip()
            line = _tier_break_runner_to_over_line(runner_name)
            if line is None:
                continue
            ou_key = _tier_break_key_to_ou_key(compare_key, line)
            if not ou_key:
                continue
            price_bundle = runner_fanduel_price_bundle(runner)
            if price_bundle.get("decimal_fr") is None:
                continue
            slot = variant_map.setdefault(
                ou_key,
                {
                    "compare_key": ou_key,
                    "market_label": label,
                    "outcomes": {},
                    "fd_line_source": "tier",
                },
            )
            bundle = {**price_bundle, "fd_tier_runner": runner_name}
            current = slot["outcomes"].get("Over")
            if current is None or float(bundle["decimal_fr"]) > float(current["decimal_fr"]):
                slot["outcomes"]["Over"] = bundle

    return variant_map


def compare_normalized_breaks(
    fr_map: dict[str, dict[str, Any]],
    fd_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for compare_key, fr_market in fr_map.items():
        if not is_comparable_break_key(compare_key):
            continue
        fd_key, fd_market, line_delta = _find_break_market_near_line(compare_key, fd_map)
        if not fd_market or fd_key is None:
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
                        "outcome": outcome,
                        "fr_market_label": fr_market["market_label_raw"],
                        "fanduel_market_label": _fanduel_break_display_label(fd_market, outcome),
                        "fanduel_compare_key": fd_key,
                        "line_delta": line_delta,
                        "best_fr_odds": float(fr_payload["odds"]),
                        "best_fr_bookmaker": fr_payload["bookmaker_label"],
                        "fanduel_odds": float(
                            fd_bundle.get("decimal_raw") or fd_bundle["decimal_fr"]
                        ),
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
        row["ligne_breaks_fr"] = format_ligne_breaks_fr(row)
    return rows


def collect_fr_only_breaks(
    fr_map: dict[str, dict[str, Any]],
    fd_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for compare_key, fr_market in fr_map.items():
        if not is_comparable_break_key(compare_key):
            continue
        fd_market = fd_map.get(compare_key)
        if not fd_market:
            _fd_key, fd_market, _delta = _find_break_market_near_line(compare_key, fd_map)
        for outcome, fr_payload in fr_market["outcomes"].items():
            if fd_market and outcome in fd_market.get("outcomes", {}):
                continue
            row = {
                "compare_key": compare_key,
                "market_family": fr_market["market_family"],
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
                "issue_fr": aces_outcome_label_fr(str(outcome)),
                "marche_fr": fr_market["market_label_raw"],
                "marche_fanduel": "",
            }
            row["ligne_breaks_fr"] = format_ligne_breaks_fr(row)
            rows.append(row)
    return rows


def collect_fd_only_breaks(
    fr_map: dict[str, dict[str, Any]],
    fd_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for compare_key, fd_market in fd_map.items():
        if not is_comparable_break_key(compare_key):
            continue
        fr_market = fr_map.get(compare_key)
        if not fr_market:
            _fr_key, fr_market, _delta = _find_break_market_near_line(compare_key, fr_map)
        for outcome, fd_bundle in fd_market.get("outcomes", {}).items():
            if fr_market and outcome in fr_market.get("outcomes", {}):
                continue
            decimal_fr = fd_bundle.get("decimal_fr")
            if decimal_fr is None:
                continue
            row = {
                "compare_key": compare_key,
                "market_family": compare_key.split("|", 1)[0],
                "outcome": outcome,
                "fr_market_label": "",
                "fanduel_market_label": _fanduel_break_display_label(fd_market, outcome),
                "best_fr_odds": None,
                "best_fr_bookmaker": "",
                "cote_fr": "",
                "bookmaker_fr": "",
                "cote_us_fanduel_ml": format_american_moneyline(fd_bundle.get("american")),
                "cote_fr_fanduel": format_french_decimal(float(decimal_fr)),
                "ecart_fr_moins_fd": "",
                "meilleur_cote": "FanDuel seul",
                "issue_fr": aces_outcome_label_fr(str(outcome)),
                "marche_fr": "",
                "marche_fanduel": _fanduel_break_display_label(fd_market, outcome),
            }
            row["ligne_breaks_fr"] = format_ligne_breaks_fr(row)
            rows.append(row)
    return rows


def attach_breaks_to_anchor_result(
    compared: dict[str, Any],
    *,
    fanduel_event: dict[str, Any] | None,
    book_events: dict[str, dict[str, Any]],
    home: str,
    away: str,
) -> dict[str, Any]:
    fr_map = build_best_fr_breaks_map(book_events, home=home, away=away) if book_events else {}
    fd_map = build_fanduel_breaks_normalized_map(fanduel_event) if fanduel_event else {}
    comparable = compare_normalized_breaks(fr_map, fd_map)
    fr_only = collect_fr_only_breaks(fr_map, fd_map)
    fd_only = collect_fd_only_breaks(fr_map, fd_map)
    match_name = compared.get("match", "")
    for row in comparable + fr_only + fd_only:
        row["match"] = match_name
    compared["comparable_break_count"] = len(comparable)
    compared["comparable_breaks"] = comparable
    compared["fr_only_break_count"] = len(fr_only)
    compared["fr_only_breaks"] = fr_only
    compared["fd_only_break_count"] = len(fd_only)
    compared["fd_only_breaks"] = fd_only
    compared["fr_break_market_count"] = len(fr_map)
    compared["fd_break_market_count"] = len(fd_map)
    return compared


def build_breaks_section_payload(
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
        comparable_rows.extend(result.get("comparable_breaks", []))
        fr_only_rows.extend(result.get("fr_only_breaks", []))
        fd_only_rows.extend(result.get("fd_only_breaks", []))
        match_progress.append(
            {
                "match": result.get("match", ""),
                "comparable_count": int(result.get("comparable_break_count", 0)),
                "fr_only_count": int(result.get("fr_only_break_count", 0)),
                "fd_only_count": int(result.get("fd_only_break_count", 0)),
                "fr_market_count": int(result.get("fr_break_market_count", 0)),
                "fd_market_count": int(result.get("fd_break_market_count", 0)),
                "fanduel_found": bool(result.get("fanduel_event_id")),
            }
        )

    fr_higher_rows = collect_fr_higher_rows(comparable_rows)
    value_rows = collect_value_rows(comparable_rows, min_ev_percent=0.0)
    fd_events = sum(1 for r in results if int(r.get("fd_break_market_count", 0)) > 0)
    fr_events = sum(1 for r in results if int(r.get("fr_break_market_count", 0)) > 0)

    return {
        "source": "tennis_breaks_comparable",
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


def build_combined_payload(
    results: list[dict[str, Any]],
    *,
    partial: bool,
    anchors_total: int | None,
) -> dict[str, Any]:
    from compare_tennis_aces_vs_fanduel import build_results_payload

    aces = build_results_payload(results, partial=partial, anchors_total=anchors_total)
    breaks = build_breaks_section_payload(results, partial=partial, anchors_total=anchors_total)
    return {
        "source": "tennis_props_comparable",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "partial": partial,
        "anchors_total": anchors_total if anchors_total is not None else aces.get("anchors_total"),
        "matches_done": aces.get("matches_done", 0),
        "aces": aces,
        "breaks": breaks,
    }
