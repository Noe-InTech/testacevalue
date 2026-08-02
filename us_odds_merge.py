"""Fusion des references US : la meilleure cote decimale gagne par issue."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


SOURCE_META = {
    "fanduel": ("FanDuel", "FanDuel"),
    "rotowire": ("RotoWire", "DraftKings"),
    "bet365": ("Bet365 US", "Bet365"),
    "bet365_us": ("Bet365 US", "Bet365"),
}


def tag_us_market_map(
    variant_map: dict[str, dict[str, Any]],
    *,
    source: str,
    source_label: str | None = None,
    source_bookmaker: str | None = None,
    captured_at: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Annotate chaque marche/outcome avec la source US."""
    label, bookmaker = SOURCE_META.get(source, (source, source))
    label = source_label or label
    bookmaker = source_bookmaker or bookmaker
    tagged: dict[str, dict[str, Any]] = {}
    for key, market in variant_map.items():
        outcomes: dict[str, dict[str, Any]] = {}
        for outcome, bundle in (market.get("outcomes") or {}).items():
            outcomes[outcome] = {
                **bundle,
                "us_source": source,
                "us_source_label": label,
                "us_bookmaker": bookmaker,
            }
        tagged[key] = {
            **market,
            "source": source,
            "source_label": label,
            "source_bookmaker": bookmaker,
            "captured_at": captured_at or market.get("captured_at", ""),
            "outcomes": outcomes,
        }
    return tagged


def _bundle_decimal(bundle: dict[str, Any] | None) -> float | None:
    if not bundle:
        return None
    value = bundle.get("decimal_fr")
    if value is None:
        value = bundle.get("decimal_raw")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def merge_best_us_odds_maps(
    *maps: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """
    Fusionne N maps US normalisees.

    Pour chaque (compare_key, outcome), conserve le bundle avec la plus haute
    cote decimale FR. Les metadonnees de marche suivent la source dominante
    (ou restent mixtes si plusieurs books gagnent sur le meme marche).
    """
    merged: dict[str, dict[str, Any]] = {}
    for variant_map in maps:
        if not variant_map:
            continue
        for compare_key, market in variant_map.items():
            slot = merged.get(compare_key)
            if slot is None:
                merged[compare_key] = deepcopy(market)
                continue

            for outcome, bundle in (market.get("outcomes") or {}).items():
                current = slot["outcomes"].get(outcome)
                current_dec = _bundle_decimal(current)
                candidate_dec = _bundle_decimal(bundle)
                if candidate_dec is None:
                    continue
                if current_dec is None or candidate_dec > current_dec:
                    slot["outcomes"][outcome] = deepcopy(bundle)

            if not slot.get("market_label") and market.get("market_label"):
                slot["market_label"] = market["market_label"]
            if not slot.get("market_label_raw") and market.get("market_label_raw"):
                slot["market_label_raw"] = market["market_label_raw"]
            if not slot.get("market_family") and market.get("market_family"):
                slot["market_family"] = market["market_family"]
            if not slot.get("player_name") and market.get("player_name"):
                slot["player_name"] = market["player_name"]
            if market.get("fd_line_source") == "ou":
                slot["fd_line_source"] = "ou"

            sources = {
                str(b.get("us_source") or slot.get("source") or "")
                for b in slot["outcomes"].values()
                if b
            }
            sources.discard("")
            if len(sources) == 1:
                only = next(iter(sources))
                label, bookmaker = SOURCE_META.get(only, (only, only))
                sample = next(iter(slot["outcomes"].values()))
                slot["source"] = only
                slot["source_label"] = sample.get("us_source_label") or label
                slot["source_bookmaker"] = sample.get("us_bookmaker") or bookmaker
            elif sources:
                slot["source"] = "mixed"
                slot["source_label"] = " / ".join(
                    sorted(
                        {
                            str(b.get("us_source_label") or SOURCE_META.get(s, (s,))[0])
                            for s, b in (
                                (
                                    str(bundle.get("us_source") or ""),
                                    bundle,
                                )
                                for bundle in slot["outcomes"].values()
                            )
                            if s
                        }
                    )
                )
                slot["source_bookmaker"] = "mixed"

    return merged


def outcome_us_source_fields(fd_market: dict[str, Any], outcome: str) -> dict[str, str]:
    """Champs source US a coller sur une ligne comparable."""
    bundle = (fd_market.get("outcomes") or {}).get(outcome) or {}
    source = str(bundle.get("us_source") or fd_market.get("source") or "fanduel")
    label = str(
        bundle.get("us_source_label")
        or fd_market.get("source_label")
        or SOURCE_META.get(source, ("US",))[0]
    )
    bookmaker = str(
        bundle.get("us_bookmaker")
        or fd_market.get("source_bookmaker")
        or SOURCE_META.get(source, ("US", "US"))[1]
    )
    return {
        "us_source": source,
        "us_source_label": label,
        "us_bookmaker": bookmaker,
        "us_captured_at": str(fd_market.get("captured_at") or ""),
    }
