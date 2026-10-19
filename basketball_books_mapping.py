"""Normalisation marchés stats joueuses WNBA — books FR."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from basketball_market_mapping import (
    build_double_double_key,
    build_player_prop_key,
    build_player_tier_prop_key,
    resolve_roster_player,
    strip_accents,
    tier_threshold_to_ou_line,
)
from tennis_books_mapping import (
    NormalizedMarket,
    build_market,
    format_line,
    normalize_ou_label,
    parse_french_number,
)


def normalize_book_label(value: str) -> str:
    """Minuscules sans accents, tirets Unicode normalisés (Unibet en-dash, etc.)."""
    text = str(value or "")
    for ch in ("\u2013", "\u2014", "\u2212", "\u00ad", "\u0096", "\u0097"):
        text = text.replace(ch, " - ")
    text = strip_accents(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def _unibet_performance_family(label: str) -> str | None:
    key = normalize_book_label(label)
    family = UNIBET_PERFORMANCE_LABELS.get(key)
    if family:
        return family
    loose = re.sub(r"\s*-\s*", " ", key)
    loose = re.sub(r"\s+", " ", loose).strip()
    for dict_key, dict_family in UNIBET_PERFORMANCE_LABELS.items():
        if re.sub(r"\s*-\s*", " ", dict_key) == loose:
            return dict_family
    return None


@dataclass(frozen=True)
class PlayerPropPattern:
    family: str
    regex: re.Pattern[str]
    tier: bool = False


PLAYER_PROP_PATTERNS: tuple[PlayerPropPattern, ...] = (
    PlayerPropPattern(
        "points_player",
        re.compile(
            r"nombre de points du joueur\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
    ),
    PlayerPropPattern(
        "rebounds_player",
        re.compile(
            r"nombre de rebonds du joueur\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
    ),
    PlayerPropPattern(
        "assists_player",
        re.compile(
            r"nombre de passes decisives du joueur\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
    ),
    PlayerPropPattern(
        "threes_made_player",
        re.compile(
            r"nombre de paniers a 3 points du joueur\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
    ),
    PlayerPropPattern(
        "blocks_player",
        re.compile(
            r"nombre de contres du joueur\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
    ),
    PlayerPropPattern(
        "steals_player",
        re.compile(
            r"nombre d.?interceptions du joueur\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
    ),
    PlayerPropPattern(
        "turnovers_player",
        re.compile(
            r"nombre de pertes de balle du joueur\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
    ),
    PlayerPropPattern(
        "steals_player",
        re.compile(
            r"nombre d.?interceptions du joueur \(paliers\)\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
        tier=True,
    ),
    PlayerPropPattern(
        "blocks_player",
        re.compile(
            r"nombre de contres du joueur \(paliers\)\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
        tier=True,
    ),
    PlayerPropPattern(
        "steals_blocks_player",
        re.compile(
            r"total du joueur \(interceptions \+ contres\)\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
    ),
    PlayerPropPattern(
        "steals_blocks_player",
        re.compile(
            r"total du joueur \(interceptions \+ contres\) \(paliers\)\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
        tier=True,
    ),
    PlayerPropPattern(
        "points_rebounds_player",
        re.compile(
            r"total du joueur \(points \+ rebonds\)\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
    ),
    PlayerPropPattern(
        "points_assists_player",
        re.compile(
            r"total du joueur \(points \+ passes decisives\)\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
    ),
    PlayerPropPattern(
        "rebounds_assists_player",
        re.compile(
            r"total du joueur \(rebonds \+ passes decisives\)\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
    ),
    PlayerPropPattern(
        "rebounds_assists_player",
        re.compile(
            r"total du joueur \(passes \+ rebonds\)\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
    ),
    PlayerPropPattern(
        "pra_player",
        re.compile(
            r"total du joueur \(points \+ rebonds \+ passes decisives\)\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
    ),
    PlayerPropPattern(
        "pra_player",
        re.compile(
            r"total du joueur \(points \+ rebonds \+ passes\)\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
    ),
    PlayerPropPattern(
        "points_assists_player",
        re.compile(
            r"total du joueur \(points \+ passes\)\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
    ),
    PlayerPropPattern(
        "pra_player",
        re.compile(
            r"total du joueur \(points \+ rebonds \+ passes\)\s+\(paliers\)\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
        tier=True,
    ),
    PlayerPropPattern(
        "points_assists_player",
        re.compile(
            r"total du joueur \(points \+ passes\) \(paliers\)\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
        tier=True,
    ),
    PlayerPropPattern(
        "points_player",
        re.compile(
            r"nombre de points du joueur \(paliers\)\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
        tier=True,
    ),
    PlayerPropPattern(
        "rebounds_player",
        re.compile(
            r"nombre de rebonds du joueur \(paliers\)\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
        tier=True,
    ),
    PlayerPropPattern(
        "assists_player",
        re.compile(
            r"nombre de passes decisives du joueur \(paliers\)\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
        tier=True,
    ),
    PlayerPropPattern(
        "threes_made_player",
        re.compile(
            r"nombre de paniers a 3 points du joueur \(paliers\)\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
        tier=True,
    ),
    PlayerPropPattern(
        "points_rebounds_player",
        re.compile(
            r"total du joueur \(points \+ rebonds\) \(paliers\)\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
        tier=True,
    ),
    PlayerPropPattern(
        "points_assists_player",
        re.compile(
            r"total du joueur \(points \+ passes decisives\) \(paliers\)\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
        tier=True,
    ),
    PlayerPropPattern(
        "rebounds_assists_player",
        re.compile(
            r"total du joueur \(passes \+ rebonds\) \(paliers\)\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
        tier=True,
    ),
    PlayerPropPattern(
        "rebounds_assists_player",
        re.compile(
            r"total du joueur \(rebonds \+ passes decisives\) \(paliers\)\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
        tier=True,
    ),
    PlayerPropPattern(
        "pra_player",
        re.compile(
            r"total du joueur \(points \+ rebonds \+ passes decisives\)\s+\(paliers\)\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
        tier=True,
    ),
    PlayerPropPattern(
        "pra_player",
        re.compile(
            r"total du joueur \(points \+ rebonds \+ passes\)\s+\(paliers\)\s*-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
            re.I,
        ),
        tier=True,
    ),
)


EXCLUDED_LABEL_MARKERS = (
    "marqueur",
    "double chance",
    "meilleur marqueur",
    "meilleur rebondeur",
    "duo marqueurs",
    "trio marqueurs",
    "chaque joueur",
)


UNIBET_OU_SPECS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("points_player", re.compile(r"^plus / moins points\s*-\s*(.+?)\s*-\s*match$", re.I)),
    ("rebounds_player", re.compile(r"^plus / moins rebonds\s*-\s*(.+?)\s*-\s*match$", re.I)),
    (
        "assists_player",
        re.compile(r"^plus / moins passes decisives\s*-\s*(.+?)\s*-\s*match$", re.I),
    ),
    (
        "threes_made_player",
        re.compile(r"^\+/- paniers 3 pts reussis\s*-\s*(.+?)\s*-\s*match$", re.I),
    ),
)

UNIBET_PERFORMANCE_LABELS: dict[str, str] = {
    "performance joueur-point(s) - match": "points_player",
    "performance joueur points - match": "points_player",
    "performance joueur - rebonds - match": "rebounds_player",
    "performance joueur - passes decisives - match": "assists_player",
    "performance joueur - panier a 3pts - match": "threes_made_player",
    "performance joueur - paniers a 3pts - match": "threes_made_player",
    "performance joueur - contres - match": "blocks_player",
    "performance joueur - interceptions - match": "steals_player",
    "nbre de rebonds - joueur - match": "rebounds_player",
    "nbre de passes decisives - joueur - match": "assists_player",
    "paniers a 3 pts reussis - joueur - match": "threes_made_player",
    "performance du joueur - total points + rebonds - match": "points_rebounds_player",
    "performance du joueur - total points + passes - match": "points_assists_player",
    "performance du joueur - total rebonds + passes - match": "rebounds_assists_player",
    "performance du joueur - total points + rebonds + passes - match": "pra_player",
    "nbre de contres - joueur - match": "blocks_player",
    "nbre d'interceptions - joueur - match": "steals_player",
    "nbre d interceptions - joueur - match": "steals_player",
}

BETCLIC_OUTCOME_OU_LABELS: dict[str, str] = {
    "nombre de points du joueur (plus/moins)": "points_player",
    "nombre de rebonds du joueur (plus/moins)": "rebounds_player",
    "nombre de passes decisives du joueur (plus/moins)": "assists_player",
    "nombre de paniers a 3 points du joueur (plus/moins)": "threes_made_player",
    "total du joueur (points + rebonds) (plus/moins)": "points_rebounds_player",
    "total du joueur (points + passes) (plus/moins)": "points_assists_player",
    "total du joueur (passes + rebonds) (plus/moins)": "rebounds_assists_player",
    "total du joueur (points + rebonds + passes) (plus/moins)": "pra_player",
}

BETCLIC_OUTCOME_TIER_LABELS: dict[str, str] = {
    "nombre de points du joueur (paliers)": "points_player",
    "nombre de rebonds du joueur (paliers)": "rebounds_player",
    "nombre de passes decisives du joueur (paliers)": "assists_player",
    "nombre de paniers a 3 points du joueur (paliers)": "threes_made_player",
    "performance (pts+reb+pas) du joueur": "pra_player",
    "performance (pts+reb) du joueur": "points_rebounds_player",
    "performance (pts+pas) du joueur": "points_assists_player",
    "performance (reb+pas) du joueur": "rebounds_assists_player",
}


UNIBET_AGGREGATED_LABELS = frozenset(
    {
        "plus / moins points - joueur - match",
        "plus / moins rebonds - joueur - match",
        "plus / moins passes decisives - joueur - match",
        "plus / moins paniers a 3 points reussis - joueur - match",
        "performance joueur points - match",
        "performance joueur - rebonds - match",
        "performance joueur - passes decisives - match",
        "performance joueur - panier a 3pts - match",
        "nbre de rebonds - joueur - match",
        "nbre de passes decisives - joueur - match",
        "paniers a 3 pts reussis - joueur - match",
    }
)


def is_wnba_player_prop_label(label: str) -> bool:
    lower = normalize_book_label(label)
    if _unibet_performance_family(label):
        return True
    if lower in UNIBET_AGGREGATED_LABELS:
        return False
    if any(marker in lower for marker in EXCLUDED_LABEL_MARKERS):
        return False
    if lower == "double-double":
        return True
    if "equipe" in lower and "joueur" not in lower:
        return False
    if lower in BETCLIC_OUTCOME_OU_LABELS or lower in BETCLIC_OUTCOME_TIER_LABELS:
        return True
    if any(spec[1].search(lower) for spec in UNIBET_OU_SPECS):
        return True
    return any(pattern.regex.search(lower) for pattern in PLAYER_PROP_PATTERNS)


# Alias explicite — mêmes marchés props joueur pour WNBA et NBA.
is_basketball_player_prop_label = is_wnba_player_prop_label


def match_player_name(label: str, roster: list[str]) -> str:
    return resolve_roster_player(label, roster)


def normalized_market_to_dict(
    item: NormalizedMarket,
    roster: list[str],
) -> dict:
    outcomes = {}
    for outcome in item.outcomes:
        aligned = outcome.label
        if item.market_family.endswith("_player") and outcome.label in {"Over", "Under", "Yes"}:
            aligned = outcome.label
        elif item.player_name:
            aligned = match_player_name(outcome.label, roster) if outcome.label not in {
                "Over",
                "Under",
                "Yes",
            } else outcome.label
        outcomes[aligned] = outcome.odds
    return {
        "compare_key": item.compare_key,
        "market_family": item.market_family,
        "market_label_raw": item.market_label_raw,
        "player_name": item.player_name,
        "line": item.line,
        "outcomes": outcomes,
    }


def _parse_inline_player_line(label: str, pattern: PlayerPropPattern) -> tuple[str, str] | None:
    match = pattern.regex.search(strip_accents(label))
    if not match:
        return None
    player_name = match.group(1).strip()
    line = format_line(parse_french_number(match.group(2)) or match.group(2))
    return player_name, line


def _normalize_winamax_double_double(
    label: str,
    outcomes: Iterable[tuple[str, float | None]],
    roster: list[str],
) -> list[NormalizedMarket]:
    if strip_accents(label) != "double-double":
        return []
    markets: list[NormalizedMarket] = []
    for raw, odds in outcomes:
        if odds is None:
            continue
        player_name = match_player_name(str(raw).strip(), roster)
        market = build_market(
            build_double_double_key(player_name, roster=roster),
            "double_double_player",
            label.strip(),
            {"Yes": float(odds)},
            market_scope="player",
            player_name=player_name,
            line="0",
            period="match",
        )
        if market:
            markets.append(market)
    return markets


def _normalize_label_pattern_market(
    label: str,
    outcomes: Iterable[tuple[str, float | None]],
    roster: list[str],
) -> list[NormalizedMarket]:
    raw_label = label.strip()
    double_markets = _normalize_winamax_double_double(raw_label, outcomes, roster)
    if double_markets:
        return double_markets

    for pattern in PLAYER_PROP_PATTERNS:
        parsed = _parse_inline_player_line(raw_label, pattern)
        if not parsed:
            continue
        player_label, line = parsed
        player_name = match_player_name(player_label, roster)
        outcome_map = {
            normalize_ou_label(raw): float(odds)
            for raw, odds in outcomes
            if odds is not None
        }
        if not outcome_map:
            return []
        market = build_market(
            build_player_prop_key(pattern.family, player_name, line, roster=roster),
            pattern.family,
            raw_label,
            outcome_map,
            market_scope="player",
            player_name=player_name,
            line=line,
            period="match",
        )
        return [market] if market else []
    return []


def _normalize_outcome_player_ou_market(
    family: str,
    label: str,
    outcomes: Iterable[tuple[str, float | None]],
    roster: list[str],
) -> list[NormalizedMarket]:
    grouped: dict[tuple[str, str], dict[str, float]] = {}
    for raw, odds in outcomes:
        if odds is None:
            continue
        match = re.match(
            r"(.+?)\s*([+-])\s*de\s*([\d.,]+)",
            strip_accents(str(raw).strip()),
            flags=re.I,
        )
        if not match:
            continue
        player_name = match_player_name(match.group(1).strip(), roster)
        line = format_line(parse_french_number(match.group(3)) or match.group(3))
        outcome = "Over" if match.group(2) == "+" else "Under"
        grouped.setdefault((player_name, line), {})[outcome] = float(odds)

    markets: list[NormalizedMarket] = []
    for (player_name, line), outcome_map in grouped.items():
        market = build_market(
            build_player_prop_key(family, player_name, line, roster=roster),
            family,
            label,
            outcome_map,
            market_scope="player",
            player_name=player_name,
            line=line,
            period="match",
        )
        if market:
            markets.append(market)
    return markets


def _normalize_outcome_player_tier_market(
    family: str,
    label: str,
    outcomes: Iterable[tuple[str, float | None]],
    roster: list[str],
) -> list[NormalizedMarket]:
    markets: list[NormalizedMarket] = []
    for raw, odds in outcomes:
        if odds is None:
            continue
        text = str(raw).strip()
        player_match = re.match(r"(.+?)\s*([+-])\s*de\s*([\d.,]+)", strip_accents(text), flags=re.I)
        if player_match:
            player_name = match_player_name(player_match.group(1).strip(), roster)
            line = format_line(parse_french_number(player_match.group(3)) or player_match.group(3))
        else:
            tier_match = re.match(r"(.+?)\s+(\d+)\+$", text)
            if not tier_match:
                line_match = re.match(
                    r"^\+?\s*de\s*([\d.,]+)\s*$",
                    strip_accents(text),
                    flags=re.I,
                )
                if not line_match:
                    continue
                parsed = re.search(
                    r"-\s*(.+?)\s*\(([\d.,]+)\)\s*$",
                    strip_accents(label),
                    flags=re.I,
                )
                if not parsed:
                    continue
                player_name = match_player_name(parsed.group(1).strip(), roster)
                line = format_line(
                    parse_french_number(line_match.group(1)) or line_match.group(1)
                )
            else:
                player_name = match_player_name(tier_match.group(1).strip(), roster)
                threshold = int(tier_match.group(2))
                line = f"+{threshold}"
        if not player_name:
            continue
        compare_key = (
            build_player_tier_prop_key(family, player_name, line[1:], roster=roster)
            if str(line).startswith("+")
            else build_player_prop_key(family, player_name, line, roster=roster)
        )
        market = build_market(
            compare_key,
            family,
            label,
            {"Over": float(odds)},
            market_scope="player",
            player_name=player_name,
            line=line,
            period="match",
        )
        if market:
            markets.append(market)
    return markets


def _normalize_unibet_performance_ou_market(
    label: str,
    family: str,
    outcomes: Iterable[tuple[str, float | None]],
    roster: list[str],
) -> list[NormalizedMarket]:
    """Unibet combos PRA / P+R : « Joueur + de 36,5 » / « Joueur - de 36,5 »."""
    markets: list[NormalizedMarket] = []
    buckets: dict[tuple[str, str], dict[str, float]] = {}
    pattern = re.compile(
        r"(.+?)\s*([+-])\s*de\s*([\d.,]+)\s*$",
        flags=re.I,
    )
    for raw, odds in outcomes:
        if odds is None:
            continue
        match = pattern.match(str(raw).strip())
        if not match:
            continue
        player_name = match_player_name(match.group(1).strip(), roster)
        if not player_name:
            continue
        line = format_line(parse_french_number(match.group(3)) or match.group(3))
        side = "Over" if match.group(2) == "+" else "Under"
        buckets.setdefault((player_name, line), {})[side] = float(odds)

    for (player_name, line), outcome_map in buckets.items():
        if not outcome_map:
            continue
        market = build_market(
            build_player_prop_key(family, player_name, line, roster=roster),
            family,
            label,
            outcome_map,
            market_scope="player",
            player_name=player_name,
            line=line,
            period="match",
        )
        if market:
            markets.append(market)
    return markets


def _normalize_unibet_performance_market(
    label: str,
    family: str,
    outcomes: Iterable[tuple[str, float | None]],
    roster: list[str],
) -> list[NormalizedMarket]:
    markets: list[NormalizedMarket] = []
    for raw, odds in outcomes:
        if odds is None:
            continue
        match = re.match(r"(.+?)\s+(\d+)\+$", str(raw).strip())
        if not match:
            continue
        player_name = match_player_name(match.group(1).strip(), roster)
        threshold = int(match.group(2))
        line = f"+{threshold}"
        market = build_market(
            build_player_tier_prop_key(family, player_name, threshold, roster=roster),
            family,
            label,
            {"Over": float(odds)},
            market_scope="player",
            player_name=player_name,
            line=line,
            period="match",
        )
        if market:
            markets.append(market)
    return markets


def normalize_winamax_market(
    label: str,
    outcomes: Iterable[tuple[str, float | None]],
    roster: list[str],
) -> list[NormalizedMarket]:
    return _normalize_label_pattern_market(label, outcomes, roster)


def normalize_unibet_market(
    label: str,
    outcomes: Iterable[tuple[str, float | None]],
    roster: list[str],
) -> list[NormalizedMarket]:
    raw_label = label.strip()
    lower = normalize_book_label(raw_label)

    for family, pattern in UNIBET_OU_SPECS:
        match = pattern.search(lower)
        if not match:
            continue
        player_name = match_player_name(match.group(1).strip(), roster)
        outcome_map: dict[str, float] = {}
        for raw, odds in outcomes:
            if odds is None:
                continue
            aligned = normalize_ou_label(str(raw))
            if aligned not in {"Over", "Under"}:
                continue
            outcome_map[aligned] = float(odds)
        if not outcome_map:
            return []
        if (
            "Over" in outcome_map
            and "Under" in outcome_map
            and outcome_map["Over"] == outcome_map["Under"]
        ):
            return []
        line_value = ""
        for raw, _odds in outcomes:
            line_match = re.search(
                r"(?:Plus|Moins)(?:\s+de)?\s+([\d.,]+)",
                str(raw),
                flags=re.I,
            )
            if not line_match:
                continue
            parsed = parse_french_number(line_match.group(1))
            if parsed is not None:
                line_value = format_line(parsed)
                break
        if not line_value:
            return []
        market = build_market(
            build_player_prop_key(family, player_name, line_value, roster=roster),
            family,
            raw_label,
            outcome_map,
            market_scope="player",
            player_name=player_name,
            line=line_value,
            period="match",
        )
        return [market] if market else []

    family = _unibet_performance_family(raw_label)
    if family:
        tier_markets = _normalize_unibet_performance_market(
            raw_label,
            family,
            outcomes,
            roster,
        )
        if tier_markets:
            return tier_markets
        ou_markets = _normalize_unibet_performance_ou_market(
            raw_label,
            family,
            outcomes,
            roster,
        )
        if ou_markets:
            return ou_markets
        return []

    return _normalize_label_pattern_market(label, outcomes, roster)


def normalize_betclic_market(
    label: str,
    outcomes: Iterable[tuple[str, float | None]],
    roster: list[str],
) -> list[NormalizedMarket]:
    raw_label = label.strip()
    lower = normalize_book_label(raw_label)

    family = BETCLIC_OUTCOME_OU_LABELS.get(lower)
    if family:
        markets = _normalize_outcome_player_ou_market(family, raw_label, outcomes, roster)
        if markets:
            return markets

    family = BETCLIC_OUTCOME_TIER_LABELS.get(lower)
    if family:
        return _normalize_outcome_player_tier_market(family, raw_label, outcomes, roster)

    return _normalize_label_pattern_market(label, outcomes, roster)


BOOK_NORMALIZERS = {
    "unibet": normalize_unibet_market,
    "betclic": normalize_betclic_market,
    "winamax": normalize_winamax_market,
}
