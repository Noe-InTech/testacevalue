"""Normalisation des marchés tennis Unibet / Betclic / Winamax."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable

from tennis_market_mapping import normalize_player, player_tokens, players_match

ADVANCED_FAMILIES = {
    "aces_total",
    "aces_player",
    "aces_h2h",
    "breaks_total",
    "breaks_player",
    "first_break",
    "break_each_set",
    "tie_break_set",
    "tie_break_match",
    "service_game_result",
    "double_faults_total",
    "double_faults_player",
}


@dataclass(frozen=True)
class NormalizedOutcome:
    label: str
    odds: float


@dataclass(frozen=True)
class NormalizedMarket:
    compare_key: str
    market_family: str
    market_label_raw: str
    market_scope: str
    player_name: str
    line: str
    period: str
    outcomes: tuple[NormalizedOutcome, ...]


def strip_accents(value: str) -> str:
    return (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def parse_french_number(text: str) -> float | None:
    match = re.search(r"(\d+(?:[.,]\d+)?)", text or "")
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def format_line(value: float | str) -> str:
    number = float(str(value).replace(",", "."))
    if number.is_integer():
        return str(int(number))
    return str(number)


def extract_set_period(label: str) -> str:
    lower = strip_accents(label)
    leading = re.match(r"^(\d+)(?:er|e|eme|ème)?\s+set\b", lower)
    if leading:
        return f"set{leading.group(1)}"
    if "1er set" in lower or "set 1" in lower:
        return "set1"
    if "2e set" in lower or "2eme set" in lower or "set 2" in lower:
        return "set2"
    if "3e set" in lower or "3eme set" in lower or "set 3" in lower:
        return "set3"
    if "4e set" in lower or "4eme set" in lower or "set 4" in lower:
        return "set4"
    if "live" in lower and "set" in lower:
        live_set = re.search(r"live\s+(\d+)(?:e|eme|ème)?\s+set", lower)
        if live_set:
            return f"set{live_set.group(1)}"
    if "match" in lower:
        return "match"
    return ""


def normalize_ou_label(label: str) -> str:
    lower = strip_accents(label)
    if lower.startswith("plus") or lower.startswith("+ de") or lower.startswith("over"):
        return "Over"
    if lower.startswith("moins") or lower.startswith("- de") or lower.startswith("under"):
        return "Under"
    if lower in {"oui", "yes"}:
        return "Oui"
    if lower in {"non", "no"}:
        return "Non"
    if "remporte son jeu de service" in lower or "gagne son service" in lower:
        return "Hold"
    if "se fait breaker" in lower or "est break" in lower:
        return "Break"
    return label.strip()


def is_set_level_tiebreak_question(label: str) -> bool:
    lower = strip_accents(label)
    if "dans le set" in lower:
        return True
    if re.search(r"tie[- ]?break.*\b(1er|2e|2eme|3e)\s+set\b", lower):
        return True
    if re.search(r"\b(1er|2e|2eme|3e)\s+set\b.*tie[- ]?break", lower):
        return True
    return False


def is_match_level_tiebreak_yes_no(label: str) -> bool:
    """Oui/Non « au moins un tie-break » sur le match (≈ Over/Under 0,5)."""
    lower = strip_accents(label)
    if not ("tie-break" in lower or "tie break" in lower):
        return False
    if "plus / moins" in lower or lower.startswith("nombre de tie-break"):
        return False
    if is_set_level_tiebreak_question(label):
        return False
    if "y aura-t-il" in lower or "au moins" in lower:
        return True
    if "au cours du match" in lower:
        return True
    return False


def group_match_tiebreak_yes_no_outcomes(
    outcomes: Iterable[tuple[str, float | None]],
) -> dict[str, float]:
    yes_no_to_ou = {"Oui": "Over", "Non": "Under", "Yes": "Over", "No": "Under"}
    outcome_map: dict[str, float] = {}
    for raw, odds in outcomes:
        if odds is None:
            continue
        aligned = yes_no_to_ou.get(normalize_ou_label(raw), normalize_ou_label(raw))
        if aligned in {"Over", "Under"}:
            outcome_map[aligned] = float(odds)
    return outcome_map


def append_match_tiebreak_yes_no_market(
    markets: list[NormalizedMarket],
    raw_label: str,
    outcomes: Iterable[tuple[str, float | None]],
) -> bool:
    outcome_map = group_match_tiebreak_yes_no_outcomes(outcomes)
    if set(outcome_map) != {"Over", "Under"}:
        return False
    market = build_market(
        "tie_break_match|0.5",
        "tie_break_match",
        raw_label,
        outcome_map,
        market_scope="match",
        line="0.5",
        period="match",
    )
    if market:
        markets.append(market)
        return True
    return False


def player_key(name: str) -> str:
    tokens = player_tokens(name)
    if not tokens:
        return strip_accents(name).replace(" ", "_")
    parts = re.split(r"[\s.]+", strip_accents(name).lower())
    parts = [part for part in parts if len(part) >= 3]
    if parts and parts[-1] in tokens:
        return parts[-1]
    return max(tokens, key=len)


def match_player_name(label: str, home_player: str, away_player: str) -> str:
    if players_match(label, home_player):
        return home_player
    if players_match(label, away_player):
        return away_player
    return label.strip()


def group_over_under_outcomes(
    outcomes: Iterable[tuple[str, float | None]],
) -> dict[str, dict[str, float]]:
    grouped: dict[str, dict[str, float]] = {}
    for raw_label, odds in outcomes:
        if odds is None:
            continue
        line = parse_french_number(raw_label)
        if line is None:
            continue
        key = format_line(line)
        grouped.setdefault(key, {})[normalize_ou_label(raw_label)] = float(odds)
    return grouped


def group_tier_over_outcomes(
    outcomes: Iterable[tuple[str, float | None]],
) -> dict[str, dict[str, float]]:
    """Betclic '+ de X,Y' sans Under associe."""
    grouped: dict[str, dict[str, float]] = {}
    for raw_label, odds in outcomes:
        if odds is None:
            continue
        line = parse_french_number(raw_label)
        if line is None:
            continue
        key = format_line(line)
        grouped.setdefault(key, {})["Over"] = float(odds)
    return grouped


def build_market(
    compare_key: str,
    market_family: str,
    market_label_raw: str,
    outcome_map: dict[str, float],
    *,
    market_scope: str = "",
    player_name: str = "",
    line: str = "",
    period: str = "",
) -> NormalizedMarket | None:
    if not outcome_map:
        return None
    outcomes = tuple(
        NormalizedOutcome(label=label, odds=odds)
        for label, odds in sorted(outcome_map.items())
    )
    return NormalizedMarket(
        compare_key=compare_key,
        market_family=market_family,
        market_label_raw=market_label_raw,
        market_scope=market_scope,
        player_name=player_name,
        line=line,
        period=period,
        outcomes=outcomes,
    )


def normalize_unibet_market(
    label: str,
    outcomes: Iterable[tuple[str, float | None]],
    home_player: str,
    away_player: str,
) -> list[NormalizedMarket]:
    raw_label = label.strip()
    lower = strip_accents(raw_label)
    period = extract_set_period(raw_label)
    markets: list[NormalizedMarket] = []

    if lower in {"vainqueur du match", "vainqueur"} or "face a face" in lower:
        outcome_map = {}
        for raw, odds in outcomes:
            if odds is None:
                continue
            outcome_map[match_player_name(raw, home_player, away_player)] = float(odds)
        market = build_market("h2h", "h2h", raw_label, outcome_map, market_scope="match", period="match")
        if market:
            markets.append(market)
        return markets

    if "les deux joueurs gagnent un set" in lower:
        outcome_map = {
            normalize_ou_label(raw): float(odds)
            for raw, odds in outcomes
            if odds is not None
        }
        market = build_market(
            "both_win_set",
            "sets",
            raw_label,
            outcome_map,
            market_scope="match",
            period="match",
        )
        if market:
            markets.append(market)
        return markets

    if "plus / moins breaks" in lower and "break(s)" not in lower:
        for line, outcome_map in group_over_under_outcomes(outcomes).items():
            market = build_market(
                f"breaks_total|{line}",
                "breaks_total",
                raw_label,
                outcome_map,
                market_scope="match",
                line=line,
                period="match",
            )
            if market:
                markets.append(market)
        return markets

    player_break = re.search(
        r"plus / moins\s+([\d,]+)\s+break\(s\)\s*-\s*([^-]+?)\s*-\s*match",
        lower,
    )
    if player_break:
        line = format_line(player_break.group(1))
        player_label = player_break.group(2).strip()
        player_name = match_player_name(player_label, home_player, away_player)
        outcome_map = {
            normalize_ou_label(raw): float(odds)
            for raw, odds in outcomes
            if odds is not None
        }
        market = build_market(
            f"breaks_player|{player_key(player_name)}|{line}",
            "breaks_player",
            raw_label,
            outcome_map,
            market_scope="player",
            player_name=player_name,
            line=line,
            period="match",
        )
        if market:
            markets.append(market)
        return markets

    if ("1er joueur" in lower or "premier joueur" in lower or "premier break" in lower) and "break" in lower:
        outcome_map = {}
        for raw, odds in outcomes:
            if odds is None:
                continue
            outcome_map[match_player_name(raw, home_player, away_player)] = float(odds)
        market = build_market(
            "first_break",
            "first_break",
            raw_label,
            outcome_map,
            market_scope="match",
            period="match",
        )
        if market:
            markets.append(market)
        return markets

    if "plus / moins tie-break" in lower or "plus / moins tie break" in lower:
        for line, outcome_map in group_over_under_outcomes(outcomes).items():
            market = build_market(
                f"tie_break_match|{line}",
                "tie_break_match",
                raw_label,
                outcome_map,
                market_scope="match",
                line=line,
                period="match",
            )
            if market:
                markets.append(market)
        return markets

    if is_match_level_tiebreak_yes_no(raw_label):
        if append_match_tiebreak_yes_no_market(markets, raw_label, outcomes):
            return markets

    if "tie-break" in lower or "tie break" in lower:
        outcome_map = {
            normalize_ou_label(raw): float(odds)
            for raw, odds in outcomes
            if odds is not None
        }
        set_number = "1" if period == "set1" else period.replace("set", "") or "1"
        market = build_market(
            f"tie_break_set|{set_number}",
            "tie_break_set",
            raw_label,
            outcome_map,
            market_scope="set",
            period=period or f"set{set_number}",
        )
        if market:
            markets.append(market)
        return markets

    if "jeu de service" in lower:
        player_match = re.search(r"-\s*([^-]+?)\s*-\s*(?:1er|2e|3e)?\s*set", raw_label, flags=re.I)
        player_name = match_player_name(player_match.group(1).strip(), home_player, away_player) if player_match else ""
        set_number = "1" if period == "set1" else period.replace("set", "") or "1"
        outcome_map = {
            normalize_ou_label(raw): float(odds)
            for raw, odds in outcomes
            if odds is not None
        }
        market = build_market(
            f"service_game_result|{player_key(player_name)}|{set_number}|1",
            "service_game_result",
            raw_label,
            outcome_map,
            market_scope="game",
            player_name=player_name,
            period=period or f"set{set_number}",
        )
        if market:
            markets.append(market)
        return markets

    if "ace" in lower:
        inline_player = re.match(
            r"plus / moins \(aces\) - (.+?) ([\d,.]+)\s*(?:-\s*match\s*)?$",
            lower,
        )
        if inline_player:
            player_name = match_player_name(inline_player.group(1).strip(), home_player, away_player)
            line = format_line(parse_french_number(inline_player.group(2)))
            outcome_map = {
                normalize_ou_label(raw): float(odds)
                for raw, odds in outcomes
                if odds is not None
            }
            ace_period = extract_set_period(raw_label)
            if ace_period.startswith("set"):
                set_number = ace_period.replace("set", "")
                market = build_market(
                    f"aces_set_player|{set_number}|{player_key(player_name)}|{line}",
                    "aces_set_player",
                    raw_label,
                    outcome_map,
                    market_scope="set_player",
                    player_name=player_name,
                    line=line,
                    period=ace_period,
                )
            else:
                market = build_market(
                    f"aces_player|{player_key(player_name)}|{line}",
                    "aces_player",
                    raw_label,
                    outcome_map,
                    market_scope="player",
                    player_name=player_name,
                    line=line,
                    period="match",
                )
            if market:
                markets.append(market)
            return markets

        if "joueur" in lower and "set" in lower:
            return markets

        player_match = re.search(r"-\s*([^-]+?)\s*-\s*match", raw_label, flags=re.I)
        if "plus / moins" in lower and player_match:
            player_name = match_player_name(player_match.group(1).strip(), home_player, away_player)
            line_value = parse_french_number(raw_label)
            line = format_line(line_value) if line_value is not None else ""
            outcome_map = {
                normalize_ou_label(raw): float(odds)
                for raw, odds in outcomes
                if odds is not None
            }
            market = build_market(
                f"aces_player|{player_key(player_name)}|{line}",
                "aces_player",
                raw_label,
                outcome_map,
                market_scope="player",
                player_name=player_name,
                line=line,
                period="match",
            )
            if market:
                markets.append(market)
            return markets
        if "plus / moins" in lower:
            for line, outcome_map in group_over_under_outcomes(outcomes).items():
                market = build_market(
                    f"aces_total|{line}",
                    "aces_total",
                    raw_label,
                    outcome_map,
                    market_scope="match",
                    line=line,
                    period="match",
                )
                if market:
                    markets.append(market)
            return markets

    if "nombre total de jeux" in lower or "total jeux" in lower or "nombre de jeux" in lower:
        for line, outcome_map in group_over_under_outcomes(outcomes).items():
            market = build_market(
                f"games_total|{line}",
                "games_total",
                raw_label,
                outcome_map,
                market_scope="match",
                line=line,
                period="match",
            )
            if market:
                markets.append(market)
        return markets

    if "plus / moins jeux" in lower and "joueur" not in lower:
        if period == "match":
            for line, outcome_map in group_over_under_outcomes(outcomes).items():
                market = build_market(
                    f"games_total|{line}",
                    "games_total",
                    raw_label,
                    outcome_map,
                    market_scope="match",
                    line=line,
                    period="match",
                )
                if market:
                    markets.append(market)
            return markets
        if period == "set1":
            for line, outcome_map in group_over_under_outcomes(outcomes).items():
                market = build_market(
                    f"set1_totals|{line}",
                    "games_total",
                    raw_label,
                    outcome_map,
                    market_scope="set",
                    line=line,
                    period="set1",
                )
                if market:
                    markets.append(market)
            return markets

    if "plus / moins set" in lower and period == "match":
        for line, outcome_map in group_over_under_outcomes(outcomes).items():
            market = build_market(
                f"total_sets|{line}",
                "sets",
                raw_label,
                outcome_map,
                market_scope="match",
                line=line,
                period="match",
            )
            if market:
                markets.append(market)
        return markets

    if re.search(r"(^| )1er set( |$)", lower) and ("vainqueur" in lower or "gagnant" in lower) and "apres" not in lower:
        outcome_map = {}
        for raw, odds in outcomes:
            if odds is None:
                continue
            outcome_map[match_player_name(raw, home_player, away_player)] = float(odds)
        market = build_market(
            "set1_winner",
            "sets",
            raw_label,
            outcome_map,
            market_scope="set",
            period="set1",
        )
        if market:
            markets.append(market)
        return markets

    return markets


def normalize_betclic_market(
    label: str,
    outcomes: Iterable[tuple[str, float | None]],
    home_player: str,
    away_player: str,
) -> list[NormalizedMarket]:
    raw_label = label.strip()
    lower = strip_accents(raw_label)
    markets: list[NormalizedMarket] = []

    if lower == "vainqueur du match":
        outcome_map = {}
        for raw, odds in outcomes:
            if odds is None:
                continue
            outcome_map[match_player_name(raw, home_player, away_player)] = float(odds)
        market = build_market("h2h", "h2h", raw_label, outcome_map, market_scope="match", period="match")
        if market:
            markets.append(market)
        return markets

    if lower == "nombre total de jeux":
        for line, outcome_map in group_over_under_outcomes(outcomes).items():
            market = build_market(
                f"games_total|{line}",
                "games_total",
                raw_label,
                outcome_map,
                market_scope="match",
                line=line,
                period="match",
            )
            if market:
                markets.append(market)
        return markets

    if "1er set" in lower and "vainqueur" in lower:
        outcome_map = {}
        for raw, odds in outcomes:
            if odds is None:
                continue
            outcome_map[match_player_name(raw, home_player, away_player)] = float(odds)
        market = build_market(
            "set1_winner",
            "sets",
            raw_label,
            outcome_map,
            market_scope="set",
            period="set1",
        )
        if market:
            markets.append(market)
        return markets

    if "2eme set" in lower and "vainqueur" in lower:
        outcome_map = {}
        for raw, odds in outcomes:
            if odds is None:
                continue
            outcome_map[match_player_name(raw, home_player, away_player)] = float(odds)
        market = build_market(
            "set2_winner",
            "sets",
            raw_label,
            outcome_map,
            market_scope="set",
            period="set2",
        )
        if market:
            markets.append(market)
        return markets

    if lower == "les deux joueurs gagnent un set":
        outcome_map = {
            normalize_ou_label(raw): float(odds)
            for raw, odds in outcomes
            if odds is not None
        }
        market = build_market(
            "both_win_set",
            "sets",
            raw_label,
            outcome_map,
            market_scope="match",
            period="match",
        )
        if market:
            markets.append(market)
        return markets

    if "nombre total de jeux" in lower and "1er set" in lower:
        for line, outcome_map in group_over_under_outcomes(outcomes).items():
            market = build_market(
                f"set1_totals|{line}",
                "games_total",
                raw_label,
                outcome_map,
                market_scope="set",
                line=line,
                period="set1",
            )
            if market:
                markets.append(market)
        return markets

    if lower.startswith("nombre total de breaks"):
        for line, outcome_map in group_over_under_outcomes(outcomes).items():
            market = build_market(
                f"breaks_total|{line}",
                "breaks_total",
                raw_label,
                outcome_map,
                market_scope="match",
                line=line,
                period="match",
            )
            if market:
                markets.append(market)
        return markets

    player_break = re.search(r"nombre total de breaks de\s+(.+)$", lower)
    if not player_break:
        player_break = re.search(r"^(.+?)\s*-\s*nombre total de breaks$", lower)
    if player_break:
        player_name = match_player_name(player_break.group(1).strip(), home_player, away_player)
        for line, outcome_map in group_over_under_outcomes(outcomes).items():
            market = build_market(
                f"breaks_player|{player_key(player_name)}|{line}",
                "breaks_player",
                raw_label,
                outcome_map,
                market_scope="player",
                player_name=player_name,
                line=line,
                period="match",
            )
            if market:
                markets.append(market)
        return markets

    if "plus / moins breaks" in lower and "break(s)" not in lower:
        for line, outcome_map in group_over_under_outcomes(outcomes).items():
            market = build_market(
                f"breaks_total|{line}",
                "breaks_total",
                raw_label,
                outcome_map,
                market_scope="match",
                line=line,
                period="match",
            )
            if market:
                markets.append(market)
        return markets

    player_break = re.search(
        r"plus / moins\s+([\d,]+)\s+break\(s\)\s*-\s*([^-]+?)\s*-\s*match",
        lower,
    )
    if player_break:
        line = format_line(player_break.group(1))
        player_name = match_player_name(player_break.group(2).strip(), home_player, away_player)
        outcome_map = {
            normalize_ou_label(raw): float(odds)
            for raw, odds in outcomes
            if odds is not None
        }
        market = build_market(
            f"breaks_player|{player_key(player_name)}|{line}",
            "breaks_player",
            raw_label,
            outcome_map,
            market_scope="player",
            player_name=player_name,
            line=line,
            period="match",
        )
        if market:
            markets.append(market)
        return markets

    if ("1er joueur" in lower or "premier joueur" in lower or "premier break" in lower) and "break" in lower:
        outcome_map = {}
        for raw, odds in outcomes:
            if odds is None:
                continue
            outcome_map[match_player_name(raw, home_player, away_player)] = float(odds)
        market = build_market(
            "first_break",
            "first_break",
            raw_label,
            outcome_map,
            market_scope="match",
            period="match",
        )
        if market:
            markets.append(market)
        return markets

    if "plus / moins tie-break" in lower or "plus / moins tie break" in lower:
        for line, outcome_map in group_over_under_outcomes(outcomes).items():
            market = build_market(
                f"tie_break_match|{line}",
                "tie_break_match",
                raw_label,
                outcome_map,
                market_scope="match",
                line=line,
                period="match",
            )
            if market:
                markets.append(market)
        return markets

    if is_match_level_tiebreak_yes_no(raw_label):
        if append_match_tiebreak_yes_no_market(markets, raw_label, outcomes):
            return markets

    if "tie-break" in lower or "tie break" in lower:
        outcome_map = {
            normalize_ou_label(raw): float(odds)
            for raw, odds in outcomes
            if odds is not None
        }
        period = extract_set_period(raw_label)
        set_number = "1" if period == "set1" else period.replace("set", "") or "1"
        market = build_market(
            f"tie_break_set|{set_number}",
            "tie_break_set",
            raw_label,
            outcome_map,
            market_scope="set",
            period=period or f"set{set_number}",
        )
        if market:
            markets.append(market)
        return markets

    if "ace" in lower:
        period = extract_set_period(raw_label)
        set_number = ""
        if period.startswith("set"):
            set_number = period.replace("set", "")

        if set_number:
            player_total = re.match(
                rf"^{set_number}(?:er|e|eme|ème)?\s+set\s*-\s*(.+?)\s*-\s*nombre total d['\u2019]aces$",
                strip_accents(raw_label),
                flags=re.I,
            )
            if player_total:
                player_name = match_player_name(
                    player_total.group(1).strip(),
                    home_player,
                    away_player,
                )
                for line, outcome_map in group_tier_over_outcomes(outcomes).items():
                    market = build_market(
                        f"aces_set_player|{set_number}|{player_key(player_name)}|{line}",
                        "aces_set_player",
                        raw_label,
                        outcome_map,
                        market_scope="set_player",
                        player_name=player_name,
                        line=line,
                        period=period,
                    )
                    if market:
                        markets.append(market)
                return markets

            if re.search(rf"^{set_number}(?:er|e|eme|ème)?\s+set\s*-\s*nombre total d['\u2019]aces", strip_accents(raw_label), flags=re.I):
                for line, outcome_map in group_tier_over_outcomes(outcomes).items():
                    market = build_market(
                        f"aces_set_total|{set_number}|{line}",
                        "aces_set_total",
                        raw_label,
                        outcome_map,
                        market_scope="set",
                        line=line,
                        period=period,
                    )
                    if market:
                        markets.append(market)
                return markets

        if not period or period == "match":
            player_total = re.match(
                r"^(?:1er set|2eme set|2e set|match)\s*-\s*(.+?)\s*-\s*nombre total d['\u2019]aces$",
                raw_label,
                flags=re.I,
            )
            if player_total:
                player_name = match_player_name(
                    player_total.group(1).strip(),
                    home_player,
                    away_player,
                )
                for line, outcome_map in group_over_under_outcomes(outcomes).items():
                    market = build_market(
                        f"aces_player|{player_key(player_name)}|{line}",
                        "aces_player",
                        raw_label,
                        outcome_map,
                        market_scope="player",
                        player_name=player_name,
                        line=line,
                        period="match",
                    )
                    if market:
                        markets.append(market)
                return markets

            if re.search(r"nombre total d['\u2019]aces", lower):
                for line, outcome_map in group_over_under_outcomes(outcomes).items():
                    market = build_market(
                        f"aces_total|{line}",
                        "aces_total",
                        raw_label,
                        outcome_map,
                        market_scope="match",
                        line=line,
                        period="match",
                    )
                    if market:
                        markets.append(market)
                return markets

        player_match = re.search(r"-\s*([^-]+?)\s*-\s*match", raw_label, flags=re.I)
        if "plus / moins" in lower and player_match:
            player_name = match_player_name(player_match.group(1).strip(), home_player, away_player)
            line_value = parse_french_number(raw_label)
            line = format_line(line_value) if line_value is not None else ""
            outcome_map = {
                normalize_ou_label(raw): float(odds)
                for raw, odds in outcomes
                if odds is not None
            }
            market = build_market(
                f"aces_player|{player_key(player_name)}|{line}",
                "aces_player",
                raw_label,
                outcome_map,
                market_scope="player",
                player_name=player_name,
                line=line,
                period="match",
            )
            if market:
                markets.append(market)
            return markets
        if "plus / moins" in lower:
            for line, outcome_map in group_over_under_outcomes(outcomes).items():
                market = build_market(
                    f"aces_total|{line}",
                    "aces_total",
                    raw_label,
                    outcome_map,
                    market_scope="match",
                    line=line,
                    period="match",
                )
                if market:
                    markets.append(market)
            return markets

    return markets


def normalize_winamax_market(
    label: str,
    outcomes: Iterable[tuple[str, float | None]],
    home_player: str,
    away_player: str,
) -> list[NormalizedMarket]:
    raw_label = label.strip()
    lower = strip_accents(raw_label)
    period = extract_set_period(raw_label)
    markets: list[NormalizedMarket] = []

    if lower == "vainqueur" or lower.startswith("vainqueur ("):
        outcome_map = {}
        for raw, odds in outcomes:
            if odds is None:
                continue
            outcome_map[match_player_name(raw, home_player, away_player)] = float(odds)
        market = build_market("h2h", "h2h", raw_label, outcome_map, market_scope="match", period="match")
        if market:
            markets.append(market)
        return markets

    if "les deux joueurs gagnent un set" in lower:
        outcome_map = {
            normalize_ou_label(raw): float(odds)
            for raw, odds in outcomes
            if odds is not None
        }
        market = build_market(
            "both_win_set",
            "sets",
            raw_label,
            outcome_map,
            market_scope="match",
            period="match",
        )
        if market:
            markets.append(market)
        return markets

    if ("premier joueur" in lower or "premier break" in lower) and "break" in lower:
        outcome_map = {}
        for raw, odds in outcomes:
            if odds is None:
                continue
            outcome_map[match_player_name(raw, home_player, away_player)] = float(odds)
        market = build_market(
            "first_break",
            "first_break",
            raw_label,
            outcome_map,
            market_scope="match",
            period="match",
        )
        if market:
            markets.append(market)
        return markets

    if lower.startswith("nombre de breaks dans le match"):
        for line, outcome_map in group_over_under_outcomes(outcomes).items():
            market = build_market(
                f"breaks_total|{line}",
                "breaks_total",
                raw_label,
                outcome_map,
                market_scope="match",
                line=line,
                period="match",
            )
            if market:
                markets.append(market)
        return markets

    player_break = re.search(r"nombre de breaks de\s+(.+?)(?:\s*\(|$)", lower)
    if player_break:
        player_name = match_player_name(player_break.group(1).strip(), home_player, away_player)
        line_match = re.search(r"\(([\d.,]+)\)", raw_label)
        line = format_line(line_match.group(1)) if line_match else ""
        if not line:
            grouped = group_over_under_outcomes(outcomes)
            line = next(iter(grouped), "")
        outcome_map = {
            normalize_ou_label(raw): float(odds)
            for raw, odds in outcomes
            if odds is not None
        }
        market = build_market(
            f"breaks_player|{player_key(player_name)}|{line}",
            "breaks_player",
            raw_label,
            outcome_map,
            market_scope="player",
            player_name=player_name,
            line=line,
            period="match",
        )
        if market:
            markets.append(market)
        return markets

    if lower.startswith("nombre de tie-breaks"):
        for line, outcome_map in group_over_under_outcomes(outcomes).items():
            market = build_market(
                f"tie_break_match|{line}",
                "tie_break_match",
                raw_label,
                outcome_map,
                market_scope="match",
                line=line,
                period="match",
            )
            if market:
                markets.append(market)
        return markets

    if lower.startswith("tie-break au cours du match") or is_match_level_tiebreak_yes_no(raw_label):
        if append_match_tiebreak_yes_no_market(markets, raw_label, outcomes):
            return markets
        return markets

    if "tie-break" in lower or "tie break" in lower:
        period = extract_set_period(raw_label)
        set_hint = re.search(r"\b(1er|2e|2eme|3e)\s+set\b", lower)
        if period.startswith("set") or set_hint:
            outcome_map = {
                normalize_ou_label(raw): float(odds)
                for raw, odds in outcomes
                if odds is not None
            }
            set_number = "1" if period == "set1" else period.replace("set", "") or "1"
            if set_hint and not period.startswith("set"):
                set_token = set_hint.group(1)
                set_number = "1" if set_token == "1er" else set_token.replace("eme", "").replace("e", "")
            market = build_market(
                f"tie_break_set|{set_number}",
                "tie_break_set",
                raw_label,
                outcome_map,
                market_scope="set",
                period=period or f"set{set_number}",
            )
            if market:
                markets.append(market)
            return markets

    if lower.startswith("nombre de jeux") and " de " not in lower.replace("nombre de jeux", "", 1):
        for line, outcome_map in group_over_under_outcomes(outcomes).items():
            market = build_market(
                f"games_total|{line}",
                "games_total",
                raw_label,
                outcome_map,
                market_scope="match",
                line=line,
                period="match",
            )
            if market:
                markets.append(market)
        return markets

    if "ace" in lower:
        player_match = re.search(r"nombre d'aces de\s+(.+?)(?:\s*\(|$)", lower)
        if player_match:
            player_name = match_player_name(player_match.group(1).strip(), home_player, away_player)
            line_match = re.search(r"\(([\d.,]+)\)", raw_label)
            line = format_line(line_match.group(1)) if line_match else ""
            outcome_map = {
                normalize_ou_label(raw): float(odds)
                for raw, odds in outcomes
                if odds is not None
            }
            market = build_market(
                f"aces_player|{player_key(player_name)}|{line}",
                "aces_player",
                raw_label,
                outcome_map,
                market_scope="player",
                player_name=player_name,
                line=line,
                period="match",
            )
            if market:
                markets.append(market)
            return markets
        for line, outcome_map in group_over_under_outcomes(outcomes).items():
            market = build_market(
                f"aces_total|{line}",
                "aces_total",
                raw_label,
                outcome_map,
                market_scope="match",
                line=line,
                period="match",
            )
            if market:
                markets.append(market)
        return markets

    if "1er set" in lower and "vainqueur" in lower:
        outcome_map = {}
        for raw, odds in outcomes:
            if odds is None:
                continue
            outcome_map[match_player_name(raw, home_player, away_player)] = float(odds)
        market = build_market(
            "set1_winner",
            "sets",
            raw_label,
            outcome_map,
            market_scope="set",
            period="set1",
        )
        if market:
            markets.append(market)
        return markets

    if lower.startswith("nombre de sets"):
        for line, outcome_map in group_over_under_outcomes(outcomes).items():
            market = build_market(
                f"total_sets|{line}",
                "sets",
                raw_label,
                outcome_map,
                market_scope="match",
                line=line,
                period="match",
            )
            if market:
                markets.append(market)
        return markets

    if "1er set" in lower and "nombre de jeux" in lower:
        for line, outcome_map in group_over_under_outcomes(outcomes).items():
            market = build_market(
                f"set1_totals|{line}",
                "games_total",
                raw_label,
                outcome_map,
                market_scope="set",
                line=line,
                period="set1",
            )
            if market:
                markets.append(market)
        return markets

    return markets


def canonical_outcome_label(
    label: str,
    compare_key: str,
    home_player: str,
    away_player: str,
) -> str:
    family = compare_key.split("|", 1)[0]
    if family in {"h2h", "first_break", "set1_winner", "set2_winner"}:
        if players_match(label, home_player):
            return "home"
        if players_match(label, away_player):
            return "away"
    return normalize_ou_label(label)


def normalized_market_to_dict(
    market: NormalizedMarket,
    home_player: str = "",
    away_player: str = "",
) -> dict[str, Any]:
    return {
        "compare_key": market.compare_key,
        "market_family": market.market_family,
        "market_label_raw": market.market_label_raw,
        "market_scope": market.market_scope,
        "player_name": market.player_name,
        "line": market.line,
        "period": market.period,
        "outcomes": {
            canonical_outcome_label(item.label, market.compare_key, home_player, away_player): item.odds
            for item in market.outcomes
        },
    }


def is_advanced_compare_key(compare_key: str) -> bool:
    family = compare_key.split("|", 1)[0]
    return family in ADVANCED_FAMILIES
