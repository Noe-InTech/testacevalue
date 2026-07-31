"""Normalisation marchés foot books FR → clés comparables."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from soccer_market_mapping import (
    classify_fr_market_label,
    build_yes_player_key,
    resolve_roster_player,
)


@dataclass(frozen=True)
class NormalizedSoccerMarket:
    compare_key: str
    market_family: str
    market_label_raw: str
    player_name: str
    outcomes: dict[str, float]  # Yes -> odds


def normalize_fr_soccer_market(
    label: str,
    outcomes: list[tuple[str, float | None]],
    roster: list[str],
) -> list[NormalizedSoccerMarket]:
    family = classify_fr_market_label(label)
    if not family:
        return []
    # Player yes markets: each outcome is a player name
    if family in {
        "anytime_goalscorer",
        "first_goalscorer",
        "score_or_assist",
        "anytime_assist",
        "player_card",
    }:
        items: list[NormalizedSoccerMarket] = []
        for raw_name, odds in outcomes:
            if odds is None:
                continue
            name = str(raw_name).strip()
            if not name or "/" in name:  # skip double chance pairs
                continue
            if name.lower() in {"oui", "non", "yes", "no", "plus", "moins"}:
                continue
            player = resolve_roster_player(name, roster)
            key = build_yes_player_key(family, player)
            if not key:
                continue
            items.append(
                NormalizedSoccerMarket(
                    compare_key=key,
                    market_family=family,
                    market_label_raw=label,
                    player_name=player,
                    outcomes={"Yes": float(odds)},
                )
            )
        return items
    return []


def is_soccer_player_prop_label(label: str) -> bool:
    return classify_fr_market_label(label) is not None


def normalized_market_to_dict(item: NormalizedSoccerMarket) -> dict:
    return {
        "compare_key": item.compare_key,
        "market_family": item.market_family,
        "market_label_raw": item.market_label_raw,
        "player_name": item.player_name,
        "outcomes": item.outcomes,
    }


BOOK_NORMALIZERS: dict[str, Callable[..., list[NormalizedSoccerMarket]]] = {
    "betclic": normalize_fr_soccer_market,
    "unibet": normalize_fr_soccer_market,
    "winamax": normalize_fr_soccer_market,
}
