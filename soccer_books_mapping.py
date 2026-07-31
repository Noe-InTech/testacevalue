"""Normalisation marchés foot books FR → clés comparables."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from soccer_market_mapping import (
    build_ou_subject_key,
    build_tier_player_key,
    build_tier_subject_key,
    build_yes_player_key,
    classify_fr_market_label,
    resolve_roster_player,
    resolve_team_name,
    strip_accents,
)
@dataclass(frozen=True)
class NormalizedSoccerMarket:
    compare_key: str
    market_family: str
    market_label_raw: str
    player_name: str
    outcomes: dict[str, float]


def _parse_line_from_label(label: str) -> float | None:
    m = re.search(r"\(([\d]+(?:[.,]\d+)?)\)", label)
    if m:
        return float(m.group(1).replace(",", "."))
    m = re.search(r"(\d+[.,]\d+)", label)
    if m:
        return float(m.group(1).replace(",", "."))
    return None


def _parse_player_plus_outcome(raw: str) -> tuple[str, int] | None:
    text = str(raw or "").strip()
    m = re.match(r"^(.+?)\s+(\d+)\+\s*$", text)
    if m:
        return m.group(1).strip(), int(m.group(2))
    return None


def _ou_side(raw: str) -> str | None:
    low = strip_accents(raw).lower().strip()
    if low.startswith("plus") or low.startswith("over") or low == "oui":
        return "Over"
    if low.startswith("moins") or low.startswith("under") or low == "non":
        return "Under"
    return None


def normalize_fr_soccer_market(
    label: str,
    outcomes: list[tuple[str, float | None]],
    roster: list[str],
    *,
    home_team: str = "",
    away_team: str = "",
) -> list[NormalizedSoccerMarket]:
    family = classify_fr_market_label(label)
    if not family:
        return []

    items: list[NormalizedSoccerMarket] = []

    # Player yes boards
    if family in {
        "anytime_goalscorer",
        "first_goalscorer",
        "score_or_assist",
        "anytime_assist",
        "player_card",
    }:
        for raw_name, odds in outcomes:
            if odds is None:
                continue
            name = str(raw_name).strip()
            if not name or "/" in name:
                continue
            # Winamax assists: "Player 1+" / "Player 2+"
            plus = _parse_player_plus_outcome(name)
            if plus:
                player_raw, tier = plus
                player = resolve_roster_player(player_raw, roster)
                if family == "anytime_assist" and tier == 1:
                    key = build_yes_player_key(family, player)
                else:
                    key = build_tier_player_key(family, player, tier)
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
                continue
            if name.lower() in {"oui", "non", "yes", "no", "plus", "moins", "over", "under"}:
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

    # Player shot tiers (outcome = player, line in label)
    if family in {"shots_player", "shots_on_target_player"}:
        line = _parse_line_from_label(label)
        tier = int(line) if line is not None and float(line).is_integer() else None
        if tier is None:
            m = re.search(r"(\d+)\s*(?:\+|ou plus|or more)", strip_accents(label).lower())
            tier = int(m.group(1)) if m else None
        for raw_name, odds in outcomes:
            if odds is None:
                continue
            name = str(raw_name).strip()
            plus = _parse_player_plus_outcome(name)
            if plus:
                player_raw, t = plus
                player = resolve_roster_player(player_raw, roster)
                key = build_tier_player_key(family, player, t)
            elif tier is not None and name.lower() not in {"oui", "non", "plus", "moins"}:
                player = resolve_roster_player(name, roster)
                key = build_tier_player_key(family, player, tier)
            else:
                continue
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

    # Match / team tier (N+) or O/U
    if family in {
        "shots_match",
        "shots_team",
        "shots_on_target_match",
        "shots_on_target_team",
        "corners_match",
        "corners_team",
    }:
        line = _parse_line_from_label(label)
        subject = "match"
        if family in {"shots_team", "shots_on_target_team", "corners_team"}:
            # try extract team from label after dash
            m = re.search(r"[-–:]\s*(.+)$", label)
            subject = resolve_team_name(m.group(1).strip() if m else "", home_team, away_team)
            if not subject:
                subject = home_team or away_team or "team"

        # Outcomes may be Plus/Moins O/U, or N+ Yes boards, or team names for tier markets
        ou_pairs: dict[str, float] = {}
        for raw_name, odds in outcomes:
            if odds is None:
                continue
            name = str(raw_name).strip()
            side = _ou_side(name)
            if side and line is not None:
                ou_pairs[side] = float(odds)
                continue
            plus = _parse_player_plus_outcome(name)
            if plus:
                subj_raw, tier = plus
                subj = "match" if family.endswith("_match") else resolve_team_name(subj_raw, home_team, away_team)
                key = build_tier_subject_key(family, subj, tier)
                if key:
                    items.append(
                        NormalizedSoccerMarket(
                            compare_key=key,
                            market_family=family,
                            market_label_raw=label,
                            player_name=subj,
                            outcomes={"Yes": float(odds)},
                        )
                    )
                continue
            # "15 Or More" style without subject
            m = re.match(r"^(\d+)\s*(?:\+|or more|ou plus)", name, flags=re.I)
            if m:
                key = build_tier_subject_key(family, subject, int(m.group(1)))
                if key:
                    items.append(
                        NormalizedSoccerMarket(
                            compare_key=key,
                            market_family=family,
                            market_label_raw=label,
                            player_name=subject,
                            outcomes={"Yes": float(odds)},
                        )
                    )

        if ou_pairs and line is not None:
            key = build_ou_subject_key(family, subject, line)
            if key:
                items.append(
                    NormalizedSoccerMarket(
                        compare_key=key,
                        market_family=family,
                        market_label_raw=label,
                        player_name=subject,
                        outcomes=ou_pairs,
                    )
                )
        return items

    return items


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
