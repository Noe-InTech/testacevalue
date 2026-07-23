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
from tennis_books_mapping import strip_accents
from tennis_market_mapping import (
    map_fanduel_market_to_compare_key,
    same_tennis_player,
)

from compare_tennis_aces_vs_fanduel import (
    aces_outcome_label_fr,
    collect_fr_higher_rows,
    collect_value_rows,
    compute_paired_value_fields,
    enrich_comparable_row,
)

VICTOIRE_COMPARE_KEY = "h2h"
VICTOIRE_FAMILIES = frozenset({"h2h"})


def is_victoire_market_label(label: str) -> bool:
    """Vainqueur du match uniquement — jamais set / jeu / game face-a-face."""
    lower = strip_accents(label.lower()).strip()
    if not lower:
        return False
    # Exclure set / jeu / points (sinon on mixe des cotes ~3.20 dans le h2h match).
    if any(
        token in lower
        for token in (
            "1er set",
            "2e set",
            "2eme set",
            "3e set",
            "3eme set",
            "set 1",
            "set 2",
            "set 3",
            "jeu",
            "jeux",
            "game",
            "point",
            "tie-break",
            "tie break",
            "aces",
            "break",
        )
    ):
        return False
    if lower in {
        "vainqueur du match",
        "vainqueur",
        "moneyline",
        "match betting",
        "face a face",
        "face-a-face",
        "face a face - match",
        "face a face - live match",
    }:
        return True
    if lower.startswith("vainqueur du match"):
        return True
    if lower.startswith("vainqueur (") or lower == "vainqueur":
        return True
    if ("face a face" in lower or "face-a-face" in lower) and "match" in lower:
        return True
    return False


def _align_h2h_outcome(outcome: str, home: str, away: str) -> str:
    """Aligne une issue h2h sur le roster ancre — nom de famille, pas le prenom.

    players_match est trop large (Daria Snigur ↔ Daria Egorova) et invente des values.
    """
    raw = str(outcome or "").strip()
    if not raw:
        return ""
    if raw in {"home", "1"}:
        return home
    if raw in {"away", "2"}:
        return away
    if same_tennis_player(raw, home):
        return home
    if same_tennis_player(raw, away):
        return away
    # Abbreviation type A.Bondar ↔ Anna Bondar deja couverte par same_tennis_player.
    return ""


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
    """Best FR moneyline — exige les DEUX joueurs du match, sans fuzzy prenom."""
    if not book_events:
        return {}
    sample = next(iter(book_events.values()))
    home = home or str(sample.get("home_player") or "")
    away = away or str(sample.get("away_player") or "")
    best: dict[str, dict[str, Any]] = {}

    for bookmaker, event in book_events.items():
        for market in event.get("markets") or []:
            label = str(market.get("label") or "").strip()
            if not label or not is_victoire_market_label(label):
                continue
            pair: dict[str, dict[str, Any]] = {}
            for raw, odds in market.get("outcomes") or []:
                if odds is None:
                    continue
                aligned = _align_h2h_outcome(str(raw), home, away)
                if not aligned or aligned not in {home, away}:
                    continue
                try:
                    price = float(odds)
                except (TypeError, ValueError):
                    continue
                current = pair.get(aligned)
                if current is None or price > float(current["odds"]):
                    pair[aligned] = {
                        "odds": price,
                        "bookmaker": bookmaker,
                        "bookmaker_label": BOOK_LABELS.get(bookmaker, bookmaker),
                        "raw_outcome": str(raw),
                    }
            # Un cote orphelin (1 seul joueur aligne) = mauvais match scrape → ignorer.
            if home not in pair or away not in pair:
                continue
            slot = best.setdefault(
                VICTOIRE_COMPARE_KEY,
                {
                    "compare_key": VICTOIRE_COMPARE_KEY,
                    "market_family": "h2h",
                    "market_label_raw": label,
                    "outcomes": {},
                },
            )
            for aligned, payload in pair.items():
                current = slot["outcomes"].get(aligned)
                if current is None or float(payload["odds"]) > float(current["odds"]):
                    slot["outcomes"][aligned] = payload
                    slot["market_label_raw"] = label
    if VICTOIRE_COMPARE_KEY in best:
        outcomes = best[VICTOIRE_COMPARE_KEY].get("outcomes") or {}
        if home not in outcomes or away not in outcomes:
            best.pop(VICTOIRE_COMPARE_KEY, None)
    return best


def build_fanduel_victoires_normalized_map(
    event: dict[str, Any],
    *,
    home: str = "",
    away: str = "",
) -> dict[str, dict[str, Any]]:
    # Toujours aligner sur le roster ancre (souvent abrege FR), pas les noms FD bruts.
    home = home or str(event.get("home_player") or "")
    away = away or str(event.get("away_player") or "")
    variant_map: dict[str, dict[str, Any]] = {}

    for market in event.get("markets") or []:
        label = str(market.get("marketName") or "").strip()
        if not label:
            continue
        compare_key = map_fanduel_market_to_compare_key(market)
        if compare_key != VICTOIRE_COMPARE_KEY:
            # Filet de securite si le libelle FD varie legerement.
            lower = label.lower().replace("-", " ").strip()
            if lower.replace(" ", "") not in {"moneyline", "matchbetting"}:
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
            if not aligned or aligned not in {home, away}:
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
    if _h2h_pricing_looks_swapped_or_poisoned(fr_market, fd_market):
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


def _h2h_pricing_looks_swapped_or_poisoned(
    fr_market: dict[str, Any],
    fd_market: dict[str, Any],
) -> bool:
    """Detecte cote FR absurde vs FD (ex. jeu Unibet 3.20 vs ML FD 1.15 sur le favori)."""
    fr_outcomes = fr_market.get("outcomes") or {}
    fd_outcomes = fd_market.get("outcomes") or {}
    if len(fr_outcomes) < 2 or len(fd_outcomes) < 2:
        return False

    def _fr_odds(player: str) -> float | None:
        payload = fr_outcomes.get(player)
        if not payload:
            return None
        try:
            return float(payload["odds"])
        except (KeyError, TypeError, ValueError):
            return None

    def _fd_odds(player: str) -> float | None:
        payload = fd_outcomes.get(player)
        if not payload:
            return None
        try:
            return float(payload["decimal_fr"])
        except (KeyError, TypeError, ValueError):
            return None

    shared = [player for player in fr_outcomes if player in fd_outcomes]
    if len(shared) < 2:
        return False

    fr_fav = min(shared, key=lambda player: _fr_odds(player) or 99.0)
    fd_fav = min(shared, key=lambda player: _fd_odds(player) or 99.0)
    if fr_fav != fd_fav:
        # Favoris differents = labels probablement inverses.
        return True

    for player in shared:
        fr_o = _fr_odds(player)
        fd_o = _fd_odds(player)
        if fr_o is None or fd_o is None:
            continue
        # Favori FD net (<1.40) avec FR beaucoup plus haut → marche FR non-ML.
        if fd_o <= 1.40 and fr_o >= fd_o * 1.75:
            return True
    return False


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
    fd_map = (
        build_fanduel_victoires_normalized_map(fanduel_event, home=home, away=away)
        if fanduel_event
        else {}
    )
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
