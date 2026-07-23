"""Compare marches aces FR (Unibet/Betclic/Winamax) vs FanDuel."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from fanduel_client import (
    FANDUEL_PROPS_TABS,
    DEFAULT_TENNIS_PAGE_CANDIDATES,
    FanDuelClient,
    decimal_fr_to_american,
    format_american_moneyline,
    format_french_decimal,
    merge_event_market_payloads,
    runner_decimal_odds,
    runner_fanduel_price_bundle,
)
from scan_tennis_aces import (
    BOOK_LABELS,
    discover_anchor_events,
    discover_anchors_from_betclic_links,
    find_event_by_players,
    is_aces_market,
    merge_anchor_lists,
    pick_best_quote,
)
from tennis_books_mapping import (
    normalize_betclic_market,
    normalize_unibet_market,
    normalize_winamax_market,
    normalized_market_to_dict,
    strip_accents,
)
from tennis_market_mapping import (
    align_fr_outcome_to_fanduel,
    fanduel_aces_runner_outcome,
    format_numeric_line,
    map_fanduel_aces_market_to_compare_key,
    players_match,
)
from value_engine import remove_vig_multiplicative

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("compare_aces_fanduel")

OUTPUT_DIR = Path(__file__).parent / "output"
BETCLIC_ACES_GRPC = ("ca_ten_ptss", "ca_ten_main", "ca_ten_sets")
COMPARABLE_ACE_PREFIXES = (
    "aces_total|",
    "aces_player|",
    "aces_set_total|",
    "aces_set_player|",
)
BOOK_NORMALIZERS = {
    "unibet": normalize_unibet_market,
    "betclic": normalize_betclic_market,
    "winamax": normalize_winamax_market,
}
ACE_FAMILIES = {"aces_total", "aces_player", "aces_set_total", "aces_set_player", "aces_h2h"}
COMPARABLE_CSV_FIELDS = [
    "match",
    "ligne_aces_fr",
    "marche_fr",
    "marche_fanduel",
    "issue_fr",
    "cote_fr",
    "bookmaker_fr",
    "cote_fr_contraire",
    "cote_us_fanduel_ml",
    "cote_us_fanduel_contraire",
    "cote_fr_fanduel",
    "cote_fr_fanduel_contraire",
    "prob_fair_fanduel",
    "ev_percent",
    "ecart_fr_moins_fd",
    "meilleur_cote",
]


def opposite_ou_outcome(outcome: str) -> str | None:
    if outcome == "Over":
        return "Under"
    if outcome == "Under":
        return "Over"
    if outcome == "Oui":
        return "Non"
    if outcome == "Non":
        return "Oui"
    return None


def format_ev_percent(ev_fraction: float) -> str:
    return f"{ev_fraction * 100:+.1f}%".replace(".", ",")


def compute_paired_value_fields(
    *,
    outcome: str,
    fr_payload: dict[str, Any],
    fr_market: dict[str, Any],
    fd_market: dict[str, Any],
) -> dict[str, Any]:
    """Calcule cotes contraires et EV via paire Over/Under FanDuel (sans vig)."""
    opposite = opposite_ou_outcome(outcome)
    fields: dict[str, Any] = {
        "cote_fr_contraire": "",
        "bookmaker_fr_contraire": "",
        "cote_us_fanduel_contraire": "",
        "cote_fr_fanduel_contraire": "",
        "prob_fair_fanduel": "",
        "ev_percent": "",
        "ev_percent_raw": None,
        "paire_fd_complete": False,
        "issue_fr_contraire": "",
    }
    if not opposite:
        return fields

    fields["issue_fr_contraire"] = aces_outcome_label_fr(opposite)
    fr_opposite = fr_market["outcomes"].get(opposite)
    if fr_opposite:
        fields["cote_fr_contraire"] = format_french_decimal(float(fr_opposite["odds"]))
        fields["bookmaker_fr_contraire"] = fr_opposite.get("bookmaker_label", "")

    fd_side = fd_market["outcomes"].get(outcome)
    fd_opposite = fd_market["outcomes"].get(opposite)
    if fd_opposite:
        opp_american = fd_opposite.get("american")
        opp_decimal = fd_opposite.get("decimal_fr")
        if opp_american is None and opp_decimal is not None:
            opp_american = decimal_fr_to_american(float(opp_decimal))
        fields["cote_us_fanduel_contraire"] = format_american_moneyline(opp_american)
        if opp_decimal is not None:
            fields["cote_fr_fanduel_contraire"] = format_french_decimal(float(opp_decimal))

    if not fd_side or not fd_opposite:
        return fields

    if fd_market.get("fd_line_source") == "tier":
        return fields

    over_bundle = fd_market["outcomes"].get("Over")
    under_bundle = fd_market["outcomes"].get("Under")
    if not over_bundle or not under_bundle:
        over_bundle = over_bundle or fd_market["outcomes"].get("Oui")
        under_bundle = under_bundle or fd_market["outcomes"].get("Non")
    if not over_bundle or not under_bundle:
        return fields
    if over_bundle.get("decimal_fr") is None or under_bundle.get("decimal_fr") is None:
        return fields

    odds_pair = {
        "Over": float(over_bundle["decimal_fr"]),
        "Under": float(under_bundle["decimal_fr"]),
    }
    fair = remove_vig_multiplicative(odds_pair)
    fair_key = outcome
    if outcome in {"Oui", "Non"}:
        fair_key = "Over" if outcome == "Oui" else "Under"
    elif outcome == "Over":
        fair_key = "Over"
    elif outcome == "Under":
        fair_key = "Under"
    fair_prob = fair.get(fair_key, 0.0)
    fields["prob_fair_fanduel"] = f"{fair_prob * 100:.1f}%".replace(".", ",")
    fields["paire_fd_complete"] = True
    fr_odds = float(fr_payload["odds"])
    ev = fair_prob * fr_odds - 1.0
    fields["ev_percent"] = format_ev_percent(ev)
    fields["ev_percent_raw"] = round(ev * 100, 2)
    return fields


def aces_outcome_label_fr(outcome: str) -> str:
    mapping = {
        "Over": "Plus",
        "Under": "Moins",
        "over": "Plus",
        "under": "Moins",
    }
    return mapping.get(outcome, outcome)


def _player_label_from_token(token: str) -> str:
    cleaned = token.replace("_", " ").strip()
    if not cleaned:
        return token
    return cleaned[0].upper() + cleaned[1:]


def format_ligne_aces_fr(row: dict[str, Any]) -> str:
    """Libelle lisible du pari aces (ex. Plus de 14,5 aces — Zverev)."""
    issue = aces_outcome_label_fr(str(row.get("outcome", "")))
    compare_key = str(row.get("compare_key", ""))
    parts = compare_key.split("|")
    family = parts[0] if parts else ""

    if family == "aces_player" and len(parts) >= 3:
        player = _player_label_from_token(parts[1])
        line = parts[2].replace(".", ",")
        if issue == "Plus":
            return f"Plus de {line} aces — {player}"
        if issue == "Moins":
            return f"Moins de {line} aces — {player}"
    if family == "aces_total" and len(parts) >= 2:
        line = parts[1].replace(".", ",")
        if issue == "Plus":
            return f"Plus de {line} aces — match"
        if issue == "Moins":
            return f"Moins de {line} aces — match"

    marche = str(row.get("fr_market_label") or row.get("marche_fr", "")).strip()
    if marche and issue:
        return f"{issue} — {marche}"
    return marche or issue or compare_key


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
        "ligne_aces_fr": format_ligne_aces_fr(row),
    }
    return enriched


def has_comparable_fr_aces(fr_map: dict[str, dict[str, Any]]) -> bool:
    return any(key.startswith(COMPARABLE_ACE_PREFIXES) for key in fr_map)


def has_any_fr_aces(fr_map: dict[str, dict[str, Any]]) -> bool:
    return bool(fr_map)


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
    """In-play + competitions + pages custom (pas uniquement le live)."""
    return fanduel.list_all_tennis_events()


def _count_live_anchors(
    anchors: list[dict[str, Any]],
    unibet_meta: list[dict[str, Any]],
    winamax_links: list[Any],
) -> int:
    from unibet_client import UnibetClient

    live = 0
    for anchor in anchors:
        home = anchor["home_player"]
        away = anchor["away_player"]
        for meta in unibet_meta:
            if not UnibetClient._event_is_live(meta):
                continue
            if players_match(home, str(meta.get("home", ""))) and players_match(
                away, str(meta.get("away", ""))
            ):
                live += 1
                break
            if players_match(home, str(meta.get("away", ""))) and players_match(
                away, str(meta.get("home", ""))
            ):
                live += 1
                break
        else:
            for link in winamax_links:
                if str(getattr(link, "status", "") or "").upper() != "LIVE":
                    continue
                if players_match(home, link.home_player) and players_match(away, link.away_player):
                    live += 1
                    break
    return live


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


def _skip_fr_ace_market_label(label_lower: str) -> bool:
    lower = strip_accents(label_lower)
    if any(token in lower for token in (" jeu", "face a face", "face-a-face")):
        return True
    if any(token in lower for token in ("1er set", "2e set", "2eme set", "3e set")):
        return True
    if "joueur" in lower and "set" in lower:
        return True
    if "live" in lower and "- match" not in lower:
        return True
    return False


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
                label_lower = label.lower()
                if _skip_fr_ace_market_label(label_lower):
                    if not item.compare_key.startswith(("aces_set_total|", "aces_set_player|")):
                        continue
                if item.compare_key.startswith("aces_total|"):
                    try:
                        if float(item.compare_key.split("|", 1)[1]) < 4.0:
                            continue
                    except ValueError:
                        pass
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


def _tier_runner_to_over_line(runner_name: str) -> str | None:
    """FanDuel '13+' equivaut a Over 12.5 (seuil FR aligne)."""
    match = re.match(r"(\d+)\+", runner_name.strip().lower())
    if not match:
        return None
    tier = int(match.group(1))
    return format_numeric_line(tier - 0.5)


def _tier_compare_key_to_ou_key(compare_key: str, line: str) -> str | None:
    if compare_key == "aces_total_tiers":
        return f"aces_total|{line}"
    if compare_key.startswith("aces_player_tiers|"):
        token = compare_key.split("|", 1)[1]
        return f"aces_player|{token}|{line}"
    if compare_key.startswith("aces_set_tiers|"):
        set_number = compare_key.split("|", 1)[1]
        return f"aces_set_total|{set_number}|{line}"
    return None


def build_fanduel_normalized_map(event: dict[str, Any]) -> dict[str, dict[str, Any]]:
    home = event.get("home_player", "")
    away = event.get("away_player", "")
    variant_map: dict[str, dict[str, Any]] = {}

    for market in event.get("markets", []):
        label = str(market.get("marketName", "")).strip()
        if not label or not is_aces_market(label):
            continue
        compare_key = map_fanduel_aces_market_to_compare_key(market, home, away)
        if not compare_key:
            continue

        if not compare_key.startswith(("aces_total|", "aces_player|")):
            if compare_key not in {"aces_total_tiers"} and not compare_key.startswith(
                ("aces_player_tiers|", "aces_set_tiers|")
            ):
                continue

        if compare_key.startswith(("aces_total|", "aces_player|")):
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
                    "fd_line_source": "ou",
                }
            continue

        for runner in market.get("runners", []):
            if runner.get("runnerStatus") not in (None, "ACTIVE"):
                continue
            runner_name = str(runner.get("runnerName", "")).strip()
            line = _tier_runner_to_over_line(runner_name)
            if line is None:
                continue
            ou_key = _tier_compare_key_to_ou_key(compare_key, line)
            if not ou_key:
                continue
            price_bundle = runner_fanduel_price_bundle(runner)
            if price_bundle.get("decimal_fr") is None:
                continue
            tier_label = f"{runner_name} (tier FD)"
            slot = variant_map.setdefault(
                ou_key,
                {
                    "compare_key": ou_key,
                    "market_label": label,
                    "outcomes": {},
                    "fd_line_source": "tier",
                },
            )
            current = slot["outcomes"].get("Over")
            bundle = {
                **price_bundle,
                "fd_tier_runner": runner_name,
                "fanduel_market_label_tier": tier_label,
            }
            if current is None or float(bundle["decimal_fr"]) > float(current["decimal_fr"]):
                slot["outcomes"]["Over"] = bundle

    return variant_map


def _parse_aces_line_key(compare_key: str) -> tuple[str, str, float | None]:
    parts = compare_key.split("|")
    family = parts[0] if parts else ""
    if family == "aces_total" and len(parts) >= 2:
        try:
            return family, "", float(parts[1])
        except ValueError:
            return family, "", None
    if family == "aces_player" and len(parts) >= 3:
        try:
            return family, parts[1], float(parts[2])
        except ValueError:
            return family, parts[1], None
    if family == "aces_set_total" and len(parts) >= 3:
        try:
            return family, parts[1], float(parts[2])
        except ValueError:
            return family, parts[1], None
    if family == "aces_set_player" and len(parts) >= 4:
        try:
            return family, parts[2], float(parts[3])
        except ValueError:
            return family, parts[2], None
    return family, "", None


def _ace_player_token_match(token_a: str, token_b: str) -> bool:
    if token_a == token_b:
        return True
    if players_match(token_a.replace("_", " "), token_b.replace("_", " ")):
        return True
    if len(token_a) >= 4 and len(token_b) >= 4 and (
        token_a.startswith(token_b) or token_b.startswith(token_a)
    ):
        return True
    return False


def _find_fd_market_near_line(
    fr_compare_key: str,
    fd_map: dict[str, dict[str, Any]],
    *,
    max_delta: float = 2.0,
) -> tuple[str | None, dict[str, Any] | None, float | None]:
    exact = fd_map.get(fr_compare_key)
    if exact:
        return fr_compare_key, exact, 0.0

    family, token, line = _parse_aces_line_key(fr_compare_key)
    if line is None:
        return None, None, None

    best_key: str | None = None
    best_market: dict[str, Any] | None = None
    best_delta: float | None = None
    for fd_key, fd_market in fd_map.items():
        fd_family, fd_token, fd_line = _parse_aces_line_key(fd_key)
        if fd_family != family or fd_line is None:
            continue
        if family in {"aces_player", "aces_set_player"} and not _ace_player_token_match(token, fd_token):
            continue
        if family == "aces_set_total" and token and fd_token and token != fd_token:
            continue
        delta = abs(fd_line - line)
        if delta > max_delta:
            continue
        if best_delta is None or delta < best_delta:
            best_key = fd_key
            best_market = fd_market
            best_delta = delta
    return best_key, best_market, best_delta


def _fanduel_display_label(fd_market: dict[str, Any], outcome: str) -> str:
    base = str(fd_market.get("market_label", ""))
    bundle = fd_market.get("outcomes", {}).get(outcome, {})
    tier_runner = bundle.get("fd_tier_runner")
    if tier_runner:
        return f"{base} — {tier_runner} (tier)"
    if fd_market.get("fd_line_source") == "ou":
        return base
    return base


def compare_normalized_aces(
    fr_map: dict[str, dict[str, Any]],
    fd_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for compare_key, fr_market in fr_map.items():
        if not compare_key.startswith(COMPARABLE_ACE_PREFIXES):
            continue
        fd_key, fd_market, line_delta = _find_fd_market_near_line(compare_key, fd_map)
        if not fd_market or fd_key is None:
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
                        "fanduel_market_label": _fanduel_display_label(fd_market, outcome),
                        "fanduel_compare_key": fd_key,
                        "line_delta": line_delta,
                        "best_fr_odds": fr_odds,
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
    return rows


def collect_fr_only_aces(
    fr_map: dict[str, dict[str, Any]],
    fd_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Lignes aces FR sans equivalent FanDuel aligne (meme ligne / meme sens)."""
    rows: list[dict[str, Any]] = []
    for compare_key, fr_market in fr_map.items():
        if not compare_key.startswith(COMPARABLE_ACE_PREFIXES):
            continue
        fd_market = fd_map.get(compare_key)
        if not fd_market:
            _fd_key, fd_market, _delta = _find_fd_market_near_line(compare_key, fd_map)
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
                "ligne_aces_fr": format_ligne_aces_fr(
                    {
                        "compare_key": compare_key,
                        "outcome": outcome,
                        "fr_market_label": fr_market["market_label_raw"],
                    }
                ),
            }
            rows.append(row)
    return rows


def collect_fd_only_aces(
    fr_map: dict[str, dict[str, Any]],
    fd_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Lignes FanDuel sans equivalent FR aligne (meme ligne / meme sens)."""
    rows: list[dict[str, Any]] = []
    for compare_key, fd_market in fd_map.items():
        if not compare_key.startswith(COMPARABLE_ACE_PREFIXES):
            continue
        fr_market = fr_map.get(compare_key)
        if not fr_market:
            _fr_key, fr_market, _delta = _find_fd_market_near_line(compare_key, fr_map)
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
                "fanduel_market_label": _fanduel_display_label(fd_market, outcome),
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
                "marche_fanduel": _fanduel_display_label(fd_market, outcome),
                "ligne_aces_fr": format_ligne_aces_fr(
                    {
                        "compare_key": compare_key,
                        "outcome": outcome,
                        "fr_market_label": "",
                    }
                ),
            }
            rows.append(row)
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
    fr_only = collect_fr_only_aces(fr_map, fd_map)
    fd_only = collect_fd_only_aces(fr_map, fd_map)
    for row in comparable:
        row["match"] = match_meta["match"]
    for row in fr_only:
        row["match"] = match_meta["match"]
    for row in fd_only:
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
        "fr_only_aces": fr_only,
        "fr_only_ace_count": len(fr_only),
        "fd_only_aces": fd_only,
        "fd_only_ace_count": len(fd_only),
        "fr_ace_market_count": len(fr_map),
        "fd_ace_market_count": len(fd_map),
        "raw_best_fr_vs_fanduel": {
            "best_fr": fr_best,
            "best_fanduel": fd_best,
            "price_delta": raw_delta,
            "best_side": raw_best_side,
            "note": "Comparaison brute: marches aces potentiellement differents.",
        },
    }


def collect_fr_only_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        for row in result.get("fr_only_aces", []):
            rows.append({"match": result["match"], **row})
    return rows


def collect_comparable_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        for row in result.get("comparable_aces", []):
            rows.append({"match": result["match"], **row})
    return rows


def collect_value_rows(rows: list[dict[str, Any]], *, min_ev_percent: float = 0.0) -> list[dict[str, Any]]:
    eligible = [
        row
        for row in rows
        if row.get("paire_fd_complete") and row.get("ev_percent_raw") is not None
    ]
    eligible.sort(key=lambda row: float(row["ev_percent_raw"]), reverse=True)
    if min_ev_percent > 0:
        return [row for row in eligible if float(row["ev_percent_raw"]) > min_ev_percent]
    return eligible


def collect_fr_higher_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("best_side") == "fr"]


def collect_fd_only_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        for row in result.get("fd_only_aces", []):
            rows.append({"match": result["match"], **row})
    return rows


def build_match_progress(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        rows.append(
            {
                "match": result.get("match", ""),
                "comparable_count": int(result.get("comparable_ace_count", 0)),
                "fr_only_count": int(result.get("fr_only_ace_count", 0)),
                "fd_only_count": int(result.get("fd_only_ace_count", 0)),
                "fr_ace_market_count": int(result.get("fr_ace_market_count", 0)),
                "fd_ace_market_count": int(result.get("fd_ace_market_count", 0)),
                "fanduel_found": bool(result.get("fanduel_event_id")),
            }
        )
    return rows


def build_results_payload(
    results: list[dict[str, Any]],
    *,
    partial: bool,
    anchors_total: int | None = None,
) -> dict[str, Any]:
    comparable_rows = collect_comparable_rows(results)
    fr_higher_rows = collect_fr_higher_rows(comparable_rows)
    value_rows = collect_value_rows(comparable_rows, min_ev_percent=0.0)
    fr_only_rows = collect_fr_only_rows(results)
    fd_only_rows = collect_fd_only_rows(results)
    match_progress = build_match_progress(results)
    fd_ace_events = sum(1 for result in results if int(result.get("fd_ace_market_count", 0)) > 0)
    fr_ace_events = sum(1 for result in results if int(result.get("fr_ace_market_count", 0)) > 0)
    return {
        "source": "tennis_aces_comparable",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "partial": partial,
        "anchors_total": anchors_total if anchors_total is not None else len(match_progress),
        "matches_done": len(match_progress),
        "comparable_count": len(comparable_rows),
        "fr_higher_count": len(fr_higher_rows),
        "value_count": len(value_rows),
        "fr_only_count": len(fr_only_rows),
        "fd_only_count": len(fd_only_rows),
        "fd_ace_event_count": fd_ace_events,
        "fr_ace_event_count": fr_ace_events,
        "comparables": comparable_rows,
        "fr_higher_comparables": fr_higher_rows,
        "value_comparables": value_rows,
        "fr_only_comparables": fr_only_rows,
        "fd_only_comparables": fd_only_rows,
        "match_progress": match_progress,
    }


def write_progress_json(
    path: Path | None,
    results: list[dict[str, Any]],
    *,
    partial: bool,
    anchors_total: int | None = None,
    combined: bool = False,
) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if combined:
        from compare_tennis_breaks import build_combined_payload

        payload = build_combined_payload(
            results, partial=partial, anchors_total=anchors_total
        )
    else:
        payload = build_results_payload(
            results, partial=partial, anchors_total=anchors_total
        )
    from atomic_json import write_json_atomic

    try:
        write_json_atomic(path, payload)
    except OSError as exc:
        log.warning("Progress JSON non ecrit (%s): %s", path.name, exc)


def _player_slug_tokens(name: str) -> list[str]:
    return [token for token in re.sub(r"[^a-z0-9]+", " ", name.lower()).split() if len(token) > 1]


def find_betclic_link_for_players(links: list[Any], home: str, away: str) -> Any | None:
    for link in links:
        slug = link.slug.rsplit("-m", 1)[0].lower()
        home_tokens = _player_slug_tokens(home)[-2:]
        away_tokens = _player_slug_tokens(away)[-2:]
        if not home_tokens or not away_tokens:
            continue
        if any(token in slug for token in home_tokens) and any(token in slug for token in away_tokens):
            return link
    return None


def find_winamax_link_for_players(links: list[Any], home: str, away: str) -> Any | None:
    for link in links:
        if players_match(home, link.home_player) and players_match(away, link.away_player):
            return link
        if players_match(home, link.away_player) and players_match(away, link.home_player):
            return link
    return None


def fetch_live_listings(
    *,
    match_filter: str = "",
    on_status: Callable[[str], None] | None = None,
) -> tuple[list[dict[str, Any]], list[Any], list[dict[str, Any]], list[Any], list[Any]]:
    from betclic_client import BetclicClient
    from unibet_client import UnibetClient
    from winamax_client import WinamaxClient

    def status(message: str) -> None:
        if on_status is not None:
            on_status(message)

    unibet = UnibetClient()
    betclic = BetclicClient()
    winamax = WinamaxClient()
    fanduel = FanDuelClient()

    status("Liste des matchs tennis (rapide)...")
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

    anchors = merge_anchor_lists(
        discover_anchor_events(unibet_meta, [], winamax_links),
        discover_anchors_from_betclic_links(betclic_links),
    )
    anchors = _merge_fanduel_anchors(anchors, fanduel_event_list)
    if match_filter:
        anchors = [anchor for anchor in anchors if anchor_matches_filter(anchor, match_filter)]

    live_count = _count_live_anchors(anchors, unibet_meta, winamax_links)
    log.info(
        "%d match(s) ancres (dont %d en cours) | %d FanDuel | Betclic gRPC=%s",
        len(anchors),
        live_count,
        len(fanduel_event_list),
        ",".join(BETCLIC_ACES_GRPC),
    )
    return anchors, betclic_links, unibet_meta, winamax_links, fanduel_event_list


def _merge_fanduel_anchors(
    anchors: list[dict[str, Any]],
    fanduel_event_list: list[Any],
) -> list[dict[str, Any]]:
    merged = list(anchors)
    for event in fanduel_event_list:
        home = event.home_player
        away = event.away_player
        if not home or not away:
            continue
        found = False
        for anchor in merged:
            if players_match(home, anchor["home_player"]) and players_match(away, anchor["away_player"]):
                anchor.setdefault("sources", set()).add("fanduel")
                found = True
                break
            if players_match(home, anchor["away_player"]) and players_match(away, anchor["home_player"]):
                anchor.setdefault("sources", set()).add("fanduel")
                found = True
                break
        if found:
            continue
        merged.append(
            {
                "home_player": home,
                "away_player": away,
                "name": f"{home} - {away}",
                "sources": {"fanduel"},
                "urls": {},
                "competition": "",
            }
        )
    return merged


def _needs_full_betclic_payload(
    *,
    betclic_payload: dict[str, Any] | None,
    fr_map: dict[str, dict[str, Any]],
    fd_map: dict[str, dict[str, Any]],
    fr_break_map: dict[str, dict[str, Any]],
    fd_break_map: dict[str, dict[str, Any]],
) -> bool:
    """Betclic SSR (hors gRPC) peut porter les aces set / tie-break O/U."""
    if not betclic_payload:
        return False
    fd_props = bool(fd_map) or bool(fd_break_map)
    fr_props = bool(fr_map) or bool(fr_break_map)
    if fd_props and not fr_props:
        return True
    if fr_props and any(key.startswith("aces_set_") for key in fr_map) and not fd_map:
        return True
    if int(betclic_payload.get("grpc_category_hits", 0)) == 0 and int(
        betclic_payload.get("ssr_market_count", 0)
    ) == 0:
        return True
    return False


def _compare_anchor_live(
    anchor: dict[str, Any],
    *,
    unibet: Any,
    betclic: Any,
    winamax: Any,
    fanduel: FanDuelClient,
    unibet_meta: list[dict[str, Any]],
    betclic_links: list[Any],
    winamax_links: list[Any],
    fanduel_event_list: list[Any],
    on_partial: Callable[[dict[str, Any], str], None] | None = None,
) -> dict[str, Any]:
    home = anchor["home_player"]
    away = anchor["away_player"]
    match_key = f"{home} vs {away}"
    match_meta = {
        "match": match_key,
        "home_player": home,
        "away_player": away,
        "competition": anchor.get("competition", ""),
        "sources": anchor.get("sources", []),
        "urls": anchor.get("urls", {}),
        "best_overall": None,
    }
    book_events: dict[str, dict[str, Any]] = {}
    fr_map: dict[str, dict[str, Any]] = {}
    fanduel_event: dict[str, Any] | None = None

    from compare_tennis_breaks import (
        attach_breaks_to_anchor_result,
        build_best_fr_breaks_map,
        build_fanduel_breaks_normalized_map,
    )

    def flush_aces(step: str) -> None:
        if on_partial is None:
            return
        partial = compare_match_to_fanduel(
            match_meta,
            fanduel_event,
            book_events,
            fr_map=fr_map,
        )
        partial["match"] = match_key
        on_partial(partial, step)

    unibet_event = find_event_by_players(home, away, unibet_meta, home_key="home", away_key="away")
    if unibet_event:
        try:
            book_events["unibet"] = unibet.build_event_payload(unibet_event)
            fr_map = build_best_fr_normalized_map(book_events, home=home, away=away)
            flush_aces("unibet")
        except Exception as exc:
            log.warning("Unibet ignore %s: %s", match_key, exc)

    betclic_link = find_betclic_link_for_players(betclic_links, home, away)
    betclic_payload: dict[str, Any] | None = None
    if betclic_link:
        try:
            betclic_payload = betclic.build_event_payload(
                betclic_link.url,
                grpc_categories=BETCLIC_ACES_GRPC,
            )
            book_events["betclic"] = betclic_payload
            fr_map = build_best_fr_normalized_map(book_events, home=home, away=away)
            flush_aces("betclic")
        except Exception as exc:
            log.warning("Betclic ignore %s: %s", match_key, exc)

    winamax_link = find_winamax_link_for_players(winamax_links, home, away)
    if winamax_link:
        try:
            payloads = winamax.build_event_payloads([winamax_link])
            if payloads:
                book_events["winamax"] = payloads[0]
                fr_map = build_best_fr_normalized_map(book_events, home=home, away=away)
                flush_aces("winamax")
        except Exception as exc:
            log.warning("Winamax ignore %s: %s", match_key, exc)

    fanduel_event = fetch_fanduel_event_payload(fanduel, home, away, fanduel_event_list)
    fd_map = build_fanduel_normalized_map(fanduel_event) if fanduel_event else {}
    if not fr_map and book_events:
        fr_map = build_best_fr_normalized_map(book_events, home=home, away=away)
    if fanduel_event:
        flush_aces("fanduel")

    fr_break_map = build_best_fr_breaks_map(book_events, home=home, away=away) if book_events else {}
    fd_break_map = build_fanduel_breaks_normalized_map(fanduel_event) if fanduel_event else {}

    if betclic_link and _needs_full_betclic_payload(
        betclic_payload=betclic_payload,
        fr_map=fr_map,
        fd_map=fd_map,
        fr_break_map=fr_break_map,
        fd_break_map=fd_break_map,
    ):
        try:
            book_events["betclic"] = betclic.build_event_payload(
                betclic_link.url,
                grpc_categories=None,
            )
            fr_map = build_best_fr_normalized_map(book_events, home=home, away=away)
            fr_break_map = build_best_fr_breaks_map(book_events, home=home, away=away)
            flush_aces("betclic-full")
        except Exception as exc:
            log.warning("Betclic (full) ignore %s: %s", match_key, exc)

    compared = compare_match_to_fanduel(match_meta, fanduel_event, book_events, fr_map=fr_map)
    compared["match"] = match_key

    return attach_breaks_to_anchor_result(
        compared,
        fanduel_event=fanduel_event,
        book_events=book_events,
        home=home,
        away=away,
    )


def _compare_anchors_parallel(
    anchors: list[dict[str, Any]],
    *,
    betclic_links: list[Any],
    unibet_meta: list[dict[str, Any]],
    winamax_links: list[Any],
    fanduel_event_list: list[Any],
    on_progress: Callable[[list[dict[str, Any]], str], None] | None = None,
) -> list[dict[str, Any]]:
    from betclic_client import BetclicClient
    from unibet_client import UnibetClient
    from winamax_client import WinamaxClient

    results: list[dict[str, Any]] = []
    partial_by_match: dict[str, dict[str, Any]] = {}
    progress_lock = threading.Lock()
    unibet = UnibetClient()
    betclic = BetclicClient()
    winamax = WinamaxClient()
    fanduel = FanDuelClient()

    def notify(message: str) -> None:
        if on_progress is not None:
            on_progress(results, message)

    def snapshot_results() -> list[dict[str, Any]]:
        with progress_lock:
            return list(results) + list(partial_by_match.values())

    def notify_snapshot(message: str) -> None:
        if on_progress is None:
            return
        on_progress(snapshot_results(), message)

    if not anchors:
        return results

    def make_on_partial(match_key: str) -> Callable[[dict[str, Any], str], None]:
        def _on_partial(partial: dict[str, Any], step: str) -> None:
            with progress_lock:
                partial_by_match[match_key] = partial
            notify_snapshot(
                f"{match_key} ({step}) — {partial.get('comparable_ace_count', 0)} comparee(s)"
            )

        return _on_partial

    with ThreadPoolExecutor(max_workers=min(6, len(anchors))) as pool:
        futures = {
            pool.submit(
                _compare_anchor_live,
                anchor,
                unibet=unibet,
                betclic=betclic,
                winamax=winamax,
                fanduel=fanduel,
                unibet_meta=unibet_meta,
                betclic_links=betclic_links,
                winamax_links=winamax_links,
                fanduel_event_list=fanduel_event_list,
                on_partial=make_on_partial(f"{anchor['home_player']} vs {anchor['away_player']}"),
            ): anchor
            for anchor in anchors
        }
        for future in as_completed(futures):
            anchor = futures[future]
            match_key = f"{anchor['home_player']} vs {anchor['away_player']}"
            try:
                compared = future.result()
            except Exception as exc:
                log.warning("Compare ignore %s: %s", match_key, exc)
                with progress_lock:
                    partial_by_match.pop(match_key, None)
                continue
            with progress_lock:
                partial_by_match.pop(match_key, None)
            results.append(compared)
            log.info(
                "%s | %d comparable(s)",
                compared["match"],
                compared["comparable_ace_count"],
            )
            notify(
                f"{compared['match']} — {compared['comparable_ace_count']} comparee(s)"
                f", {compared.get('fr_only_ace_count', 0)} FR seul"
            )
    return results


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
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if anchors_total is not None:
        payload["anchors_total"] = anchors_total
    if results is not None:
        rows = collect_comparable_rows(results)
        payload["comparable_count"] = len(rows)
        payload["fr_higher_count"] = len(collect_fr_higher_rows(rows))
        payload["value_count"] = len(collect_value_rows(rows))
        payload["matches_done"] = len(results)
        payload["fr_only_count"] = sum(int(item.get("fr_only_ace_count", 0)) for item in results)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def comparable_row_to_csv(row: dict[str, Any]) -> dict[str, str]:
    return {
        "match": str(row.get("match", "")),
        "ligne_aces_fr": str(row.get("ligne_aces_fr", "")),
        "issue_fr": str(row.get("issue_fr", "")),
        "marche_fr": str(row.get("marche_fr", "")),
        "marche_fanduel": str(row.get("marche_fanduel", "")),
        "cote_fr": str(row.get("cote_fr", "")),
        "bookmaker_fr": str(row.get("bookmaker_fr", "")),
        "cote_us_fanduel_ml": str(row.get("cote_us_fanduel_ml", "")),
        "cote_us_fanduel_contraire": str(row.get("cote_us_fanduel_contraire", "")),
        "cote_fr_fanduel": str(row.get("cote_fr_fanduel", "")),
        "cote_fr_fanduel_contraire": str(row.get("cote_fr_fanduel_contraire", "")),
        "cote_fr_contraire": str(row.get("cote_fr_contraire", "")),
        "prob_fair_fanduel": str(row.get("prob_fair_fanduel", "")),
        "ev_percent": str(row.get("ev_percent", "")),
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
        "| Match | Pari aces (FR) | Equiv. FanDuel | Cote FR | Book FR | ML US FanDuel | Cote FR FanDuel | Ecart | Meilleur |",
        "| --- | --- | --- | ---: | --- | ---: | ---: | ---: | --- |",
    ]
    if not rows:
        lines.append("| *(aucune)* | | | | | | | | |")
    for row in rows:
        lines.append(
            f"| {row.get('match', '')} | {row.get('ligne_aces_fr', row.get('issue_fr', ''))} | "
            f"{row.get('marche_fanduel', '')} | "
            f"{row.get('cote_fr', '')} | {row.get('bookmaker_fr', '')} | "
            f"{row.get('cote_us_fanduel_ml', '')} | {row.get('cote_fr_fanduel', '')} | "
            f"{row.get('ecart_fr_moins_fd', '')} | {row.get('meilleur_cote', '')} |"
        )
    lines.extend(
        [
            "",
            "## 2. Cotes FR superieures a FanDuel",
            "",
            "| Match | Pari aces (FR) | Equiv. FanDuel | Cote FR | Book FR | ML US FanDuel | Cote FR FanDuel | Ecart |",
            "| --- | --- | --- | ---: | --- | ---: | ---: | ---: |",
        ]
    )
    if not fr_higher_rows:
        lines.append("| *(aucune)* | | | | | | | |")
    for row in fr_higher_rows:
        lines.append(
            f"| {row.get('match', '')} | {row.get('ligne_aces_fr', row.get('issue_fr', ''))} | "
            f"{row.get('marche_fanduel', '')} | "
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

    payload = build_results_payload(results, partial=False)
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


def fetch_fanduel_event_payload(
    fanduel: FanDuelClient,
    home: str,
    away: str,
    fanduel_event_list: list[Any],
) -> dict[str, Any] | None:
    fanduel_meta = find_fanduel_event(home, away, fanduel_event_list)
    if not fanduel_meta:
        return None
    try:
        payload = fanduel.build_event_payload(fanduel_meta, tabs=FANDUEL_PROPS_TABS)
    except Exception as exc:
        log.warning("FanDuel ignore %s vs %s: %s", home, away, exc)
        return None

    ace_count = sum(
        1
        for market in payload.get("markets", [])
        if is_aces_market(str(market.get("marketName", "")))
    )
    if ace_count == 0:
        try:
            extra = fanduel.build_event_payload(
                fanduel_meta,
                tabs=("set-betting", "same-game-parlay-", "all-markets"),
            )
            payload = merge_event_market_payloads(payload, extra)
        except Exception as exc:
            log.warning("FanDuel extra tabs ignore %s vs %s: %s", home, away, exc)
    return payload


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
    on_progress: Callable[[list[dict[str, Any]], str], None] | None = None,
) -> list[dict[str, Any]]:
    fanduel = FanDuelClient()
    pending: list[tuple[dict[str, Any], dict[str, dict[str, Any]], Any, dict[str, dict[str, Any]] | None]] = []
    results: list[dict[str, Any]] = []

    def notify(message: str) -> None:
        if on_progress is not None:
            on_progress(results, message)
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

        fanduel_meta = find_fanduel_event(home, away, fanduel_event_list)
        if not fanduel_meta:
            compared = compare_match_to_fanduel(
                match_meta,
                None,
                book_events,
                fr_map=fr_map,
            )
            results.append(compared)
            log.info("%s | %d comparable(s) (FanDuel introuvable)", compared["match"], compared["comparable_ace_count"])
            notify(
                f"{compared['match']} — {compared['comparable_ace_count']} comparee(s)"
                f", {compared.get('fr_only_ace_count', 0)} FR seul"
            )
            continue
        pending.append((match_meta, book_events, fanduel_meta, fr_map))

    if pending:
        with ThreadPoolExecutor(max_workers=min(4, len(pending))) as pool:
            futures = {
                pool.submit(
                    fanduel.build_event_payload,
                    fanduel_meta,
                    tabs=FANDUEL_PROPS_TABS,
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
                notify(
                    f"{compared['match']} — {compared['comparable_ace_count']} comparee(s)"
                    f", {compared.get('fr_only_ace_count', 0)} FR seul"
                )
    return results


def run_live_compare(
    output: Path | None = None,
    *,
    match_filter: str = "",
    progress_json: Path | None = None,
    status_json: Path | None = None,
    combined: bool = False,
) -> Path:
    anchors_total = 0

    def on_progress(results: list[dict[str, Any]], message: str) -> None:
        write_progress_json(
            progress_json,
            results,
            partial=True,
            anchors_total=anchors_total,
            combined=combined,
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
        "Chargement des matchs tennis...",
        match_filter=match_filter,
    )
    write_progress_json(progress_json, [], partial=True, combined=combined)

    def on_listing_status(message: str) -> None:
        write_run_status_file(status_json, "running", message, match_filter=match_filter)

    anchors, betclic_links, unibet_meta, winamax_links, fanduel_event_list = fetch_live_listings(
        match_filter=match_filter,
        on_status=on_listing_status,
    )
    anchors_total = len(anchors)
    write_run_status_file(
        status_json,
        "running",
        f"{anchors_total} match(s) — resultats au fil de l'eau...",
        match_filter=match_filter,
        anchors_total=anchors_total,
    )
    write_progress_json(
        progress_json, [], partial=True, anchors_total=anchors_total, combined=combined
    )
    results = _compare_anchors_parallel(
        anchors,
        betclic_links=betclic_links,
        unibet_meta=unibet_meta,
        winamax_links=winamax_links,
        fanduel_event_list=fanduel_event_list,
        on_progress=on_progress,
    )
    csv_path = _export_results(results, output)
    write_progress_json(
        progress_json, results, partial=False, anchors_total=anchors_total, combined=combined
    )
    write_run_status_file(
        status_json,
        "success",
        f"Comparaison terminee — {len(results)}/{anchors_total} match(s).",
        match_filter=match_filter,
        results=results,
        anchors_total=anchors_total,
    )
    return csv_path


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
    parser.add_argument(
        "--combined",
        action="store_true",
        help="Inclure aces + breaks dans le JSON (sections aces/breaks)",
    )
    args = parser.parse_args()
    if args.scan_json:
        run_from_scan_json(args.scan_json, args.output, match_filter=args.match or "")
    else:
        run_live_compare(
            args.output,
            match_filter=args.match or "",
            progress_json=args.progress_json,
            status_json=args.status_json,
            combined=args.combined,
        )
