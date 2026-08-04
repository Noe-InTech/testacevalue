"""Clés canoniques et alignement joueuses WNBA (FR ↔ FanDuel)."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterator

from tennis_market_mapping import format_numeric_line, players_match


def strip_accents(value: str) -> str:
    return (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def player_token(name: str) -> str:
    """Nom de famille seul (legacy). Preferer player_compare_token avec roster."""
    parts = re.split(r"[\s.]+", strip_accents(name))
    parts = [part for part in parts if part]
    if not parts:
        return "player"
    if len(parts) >= 2 and all(len(part) == 1 for part in parts[:-1]):
        return parts[-1]
    return parts[-1]


def build_player_compare_tokens(roster: list[str]) -> dict[str, str]:
    """Tokens stables ; si plusieurs joueuses partagent un nom de famille → initiale+nom."""
    grouped: dict[str, list[str]] = {}
    for raw_name in roster:
        canonical = str(raw_name or "").strip()
        if not canonical:
            continue
        last = player_token(canonical)
        grouped.setdefault(last, []).append(canonical)

    tokens: dict[str, str] = {}
    for last, names in grouped.items():
        unique_names = sorted(set(names), key=lambda item: strip_accents(item))
        if len(unique_names) == 1:
            tokens[unique_names[0]] = last
            continue
        for name in unique_names:
            parts = re.split(r"[\s.]+", strip_accents(name))
            parts = [part for part in parts if part]
            prefix = parts[0][0] if parts else "x"
            tokens[name] = f"{prefix}{last}"
    return tokens


def player_compare_token(name: str, roster: list[str] | None = None) -> str:
    text = str(name or "").strip()
    if not text:
        return "player"
    if not roster:
        return player_token(text)
    token_map = build_player_compare_tokens(roster)
    resolved = resolve_roster_player(text, roster)
    if resolved in token_map:
        return token_map[resolved]
    for roster_name, token in token_map.items():
        if strip_accents(resolved) == strip_accents(roster_name):
            return token
        if players_match(resolved, roster_name) and _unique_roster_match(resolved, roster):
            return token
    return player_token(resolved)


def _unique_roster_match(name: str, roster: list[str]) -> bool:
    matches = [candidate for candidate in roster if players_match(name, candidate)]
    return len(matches) == 1


def is_player_prop_family(family: str) -> bool:
    return family in {
        "points_player",
        "rebounds_player",
        "assists_player",
        "threes_made_player",
        "blocks_player",
        "steals_player",
        "turnovers_player",
        "points_rebounds_player",
        "points_assists_player",
        "rebounds_assists_player",
        "pra_player",
        "double_double_player",
    }


def is_comparable_player_prop_key(compare_key: str) -> bool:
    family = compare_key.split("|", 1)[0]
    return is_player_prop_family(family)


def parse_player_prop_key(compare_key: str) -> tuple[str, str, float | None]:
    parts = compare_key.split("|")
    family = parts[0] if parts else ""
    token = parts[1] if len(parts) >= 2 else ""
    line: float | None = None
    if len(parts) >= 3:
        try:
            line = float(parts[2])
        except ValueError:
            line = None
    return family, token, line


def build_player_prop_key(
    family: str,
    player_name: str,
    line: str | float,
    *,
    roster: list[str] | None = None,
) -> str:
    return f"{family}|{player_compare_token(player_name, roster)}|{format_numeric_line(line)}"


def build_double_double_key(
    player_name: str,
    *,
    roster: list[str] | None = None,
) -> str:
    return f"double_double_player|{player_compare_token(player_name, roster)}|0"


def tier_threshold_to_ou_line(threshold: int | str) -> str:
    return format_numeric_line(float(threshold) - 0.5)


def align_fr_outcome_to_fanduel(outcome: str, compare_key: str) -> str:
    family = compare_key.split("|", 1)[0]
    if not is_player_prop_family(family):
        return outcome
    if family == "double_double_player":
        return "Yes"
    lower = strip_accents(outcome)
    if lower in {"over", "under"}:
        return outcome.capitalize()
    if lower.startswith("plus"):
        return "Over"
    if lower.startswith("moins"):
        return "Under"
    if lower in {"oui", "yes"}:
        return "Yes"
    return outcome


# Rétrocompat tests / imports intermédiaires
align_fr_outcome_to_pinnacle = align_fr_outcome_to_fanduel


FD_PLAYER_PROP_SPECS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("points_player", re.compile(r"^(.+?)\s*-\s*points$", re.I)),
    ("rebounds_player", re.compile(r"^(.+?)\s*-\s*rebounds$", re.I)),
    ("assists_player", re.compile(r"^(.+?)\s*-\s*assists$", re.I)),
    ("threes_made_player", re.compile(r"^(.+?)\s*-\s*made\s*threes$", re.I)),
    ("blocks_player", re.compile(r"^(.+?)\s*-\s*blocks$", re.I)),
    ("steals_player", re.compile(r"^(.+?)\s*-\s*steals$", re.I)),
    ("turnovers_player", re.compile(r"^(.+?)\s*-\s*turnovers$", re.I)),
    ("points_rebounds_player", re.compile(r"^(.+?)\s*-\s*pts\s*\+\s*reb$", re.I)),
    ("points_assists_player", re.compile(r"^(.+?)\s*-\s*pts\s*\+\s*ast$", re.I)),
    ("rebounds_assists_player", re.compile(r"^(.+?)\s*-\s*reb\s*\+\s*ast$", re.I)),
    ("pra_player", re.compile(r"^(.+?)\s*-\s*pts\s*\+\s*reb\s*\+\s*ast$", re.I)),
)

FD_TIER_MARKET_SPECS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("points_player", re.compile(r"^to score (\d+)\+ points$", re.I)),
    ("rebounds_player", re.compile(r"^to record (\d+)\+ rebounds$", re.I)),
    ("assists_player", re.compile(r"^to record (\d+)\+ assists$", re.I)),
    ("threes_made_player", re.compile(r"^to record (\d+)\+ made threes$", re.I)),
    ("blocks_player", re.compile(r"^to record (\d+)\+ blocks$", re.I)),
    ("steals_player", re.compile(r"^to record (\d+)\+ steals$", re.I)),
)


def is_fanduel_ou_player_prop_market_name(market_name: str) -> bool:
    name = str(market_name or "").strip()
    lower = strip_accents(name)
    if not lower or lower.startswith("to score") or lower.startswith("to record"):
        return False
    if "1st qtr" in lower or "quarter" in lower:
        return False
    return any(spec[1].search(name) for spec in FD_PLAYER_PROP_SPECS)


def extract_fanduel_player_prop_line(market: dict[str, Any]) -> str | None:
    for runner in market.get("runners", []):
        handicap = runner.get("handicap")
        if handicap is not None:
            return format_numeric_line(handicap)
        match = re.search(r"([\d.]+)\s*$", str(runner.get("runnerName", "")))
        if match:
            return format_numeric_line(match.group(1))
    return None


def resolve_roster_player(player_name: str, roster: list[str] | None) -> str:
    """Resout un libelle vers un nom roster. Ne choisit pas au hasard si homonymes."""
    text = str(player_name or "").strip()
    if not text or not roster:
        return text
    exact = [
        candidate
        for candidate in roster
        if strip_accents(text) == strip_accents(str(candidate).strip())
    ]
    if len(exact) == 1:
        return exact[0]
    fuzzy_matches = [
        str(candidate).strip()
        for candidate in roster
        if players_match(text, candidate)
    ]
    # Dedup accents
    seen: set[str] = set()
    unique_fuzzy: list[str] = []
    for candidate in fuzzy_matches:
        key = strip_accents(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique_fuzzy.append(candidate)
    if len(unique_fuzzy) == 1:
        return unique_fuzzy[0]
    if len(unique_fuzzy) > 1:
        text_parts = [part for part in re.split(r"[\s.]+", strip_accents(text)) if part]
        if text_parts:
            first = text_parts[0]
            hinted = [
                candidate
                for candidate in unique_fuzzy
                if first == strip_accents(candidate).split()[0]
                or (
                    len(first) == 1
                    and strip_accents(candidate).split()
                    and strip_accents(candidate).split()[0].startswith(first)
                )
                or first in strip_accents(candidate).split()
            ]
            if len(hinted) == 1:
                return hinted[0]
        # Ambigu : ne pas coller la premiere joueuse trouvee.
        return text
    return text


def map_fanduel_market_to_compare_key(
    market: dict[str, Any],
    *,
    roster: list[str] | None = None,
) -> str | None:
    name = str(market.get("marketName", "")).strip()
    if not is_fanduel_ou_player_prop_market_name(name):
        return None
    line = extract_fanduel_player_prop_line(market)
    if not line:
        return None
    for family, pattern in FD_PLAYER_PROP_SPECS:
        match = pattern.search(name)
        if not match:
            continue
        player_name = resolve_roster_player(match.group(1).strip(), roster)
        return build_player_prop_key(family, player_name, line, roster=roster)
    return None


def fanduel_player_prop_runner_outcome(runner_name: str) -> str:
    lower = runner_name.strip().lower()
    if lower.endswith(" over") or lower.startswith("over"):
        return "Over"
    if lower.endswith(" under") or lower.startswith("under"):
        return "Under"
    return runner_name.strip()


def iter_fanduel_player_prop_slots(
    market: dict[str, Any],
    *,
    roster: list[str] | None = None,
) -> Iterator[tuple[str, str]]:
    """Yield (compare_key, outcome) for each runner FanDuel d'un marché props joueuse."""
    name = str(market.get("marketName", "")).strip()
    lower = strip_accents(name)

    compare_key = map_fanduel_market_to_compare_key(market, roster=roster)
    if compare_key:
        for runner in market.get("runners", []):
            if runner.get("runnerStatus") not in (None, "ACTIVE"):
                continue
            runner_name = str(runner.get("runnerName", "")).strip()
            yield compare_key, fanduel_player_prop_runner_outcome(runner_name)
        return

    if lower == "to record a double double":
        for runner in market.get("runners", []):
            if runner.get("runnerStatus") not in (None, "ACTIVE"):
                continue
            player_name = resolve_roster_player(str(runner.get("runnerName", "")).strip(), roster)
            yield build_double_double_key(player_name, roster=roster), "Yes"
        return

    for family, pattern in FD_TIER_MARKET_SPECS:
        match = pattern.search(name)
        if not match:
            continue
        line = tier_threshold_to_ou_line(match.group(1))
        for runner in market.get("runners", []):
            if runner.get("runnerStatus") not in (None, "ACTIVE"):
                continue
            player_name = resolve_roster_player(str(runner.get("runnerName", "")).strip(), roster)
            yield build_player_prop_key(family, player_name, line, roster=roster), "Over"
        return
