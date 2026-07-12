"""Correspondance marchés tennis Coteur ↔ FanDuel / books FR ↔ FanDuel."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

COTEUR_EXCLUDED_TYPES = {"12handi"}

COTEUR_TYPE_LABELS = {
    "12": "Vainqueur",
    "OU": "Over/Under jeux",
    "OUJ": "Over/Under jeux set",
    "HT": "Vainqueur 1er set",
    "HT1": "Vainqueur 1er set",
    "HT2": "Vainqueur 2e set",
    "EXACT": "Score exact sets",
    "BTTS": "Les 2 joueurs gagnent un set",
    "HTFT2": "Score sets",
}

COTEUR_TO_FANDUEL_BASE: dict[str, str | None] = {
    "12": "h2h",
    "OU": "total_sets",
    "OUJ": "totals",
    "HT": "set1_winner",
    "HT1": "set1_winner",
    "HT2": "set2_winner",
    "EXACT": "set_betting",
    "BTTS": "both_win_set",
    "HTFT2": None,
}


def _split_compound_tokens(name: str) -> str:
    """CarrenoBusta -> Carreno Busta pour matcher Unibet sans espace."""
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    return re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", spaced)


def player_tokens(name: str) -> set[str]:
    cleaned = _split_compound_tokens(name)
    cleaned = (
        unicodedata.normalize("NFKD", cleaned)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
        .replace(",", " ")
        .replace(".", " ")
        .replace("'", "")
        .replace("-", " ")
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    tokens: set[str] = set()
    for token in cleaned.split():
        if token in {"junior", "senior"}:
            continue
        if len(token) >= 3:
            tokens.add(token)
        elif len(token) == 2 and token.isalpha():
            tokens.add(token)
    return tokens


def normalize_player(name: str) -> str:
    tokens = sorted(player_tokens(name))
    return tokens[0] if tokens else name.lower().strip()


def players_match(name_a: str, name_b: str) -> bool:
    tokens_a = player_tokens(name_a)
    tokens_b = player_tokens(name_b)
    if tokens_a & tokens_b:
        return True
    for token_a in tokens_a:
        for token_b in tokens_b:
            if len(token_a) >= 6 and len(token_b) >= 6 and (
                token_a.startswith(token_b) or token_b.startswith(token_a)
            ):
                return True
    return False


def coteur_special_line(typename: str, special: str) -> float | str | None:
    special = (special or "").strip()
    if not special:
        return None
    if typename in ("OU",):
        try:
            return float(special.replace("-", "."))
        except ValueError:
            return special
    if typename == "OUJ":
        if special.isdigit():
            return float(f"{special}.5")
        if "-" in special:
            left, right = special.split("-", 1)
            if right == "5":
                try:
                    return float(f"{int(left)}.5")
                except ValueError:
                    pass
        try:
            return float(special.replace("-", "."))
        except ValueError:
            return special
    if typename == "12" and ":" not in special and "-" in special:
        return special.replace("-", ".")
    if typename == "12" and ":" in special:
        return special
    return special


def coteur_handicap_line(special: str) -> float | None:
    special = (special or "").strip()
    if ":" not in special:
        return None
    sides = special.split(":", 1)
    numbers = []
    for side in sides:
        side = side.replace("+", "").replace("-", ".")
        if not side or side == "0":
            continue
        try:
            numbers.append(abs(float(side)))
        except ValueError:
            return None
    if not numbers:
        return None
    return numbers[0]


def coteur_handicap_outcome_label(special: str, outcome: str, home_player: str, away_player: str) -> str:
    line = coteur_handicap_line(special)
    if line is None:
        return outcome
    left, right = special.split(":", 1)
    left_has_handicap = left not in {"", "0"}
    right_has_handicap = right not in {"", "0"}
    if left_has_handicap and not right_has_handicap:
        if outcome == "1":
            return f"{home_player} (+{line})"
        if outcome == "2":
            return f"{away_player} (-{line})"
    if right_has_handicap and not left_has_handicap:
        if outcome == "1":
            return f"{away_player} (+{line})"
        if outcome == "2":
            return f"{home_player} (-{line})"
    return outcome


def coteur_market_label(typename: str, special: str) -> str:
    base = COTEUR_TYPE_LABELS.get(typename, typename)
    if typename == "12" and ":" in (special or ""):
        line = coteur_handicap_line(special)
        if line is not None:
            return f"Handicap sets {line}"
    line = coteur_special_line(typename, special)
    if line not in (None, ""):
        return f"{base} {line}"
    return base


def coteur_outcome_label(
    typename: str,
    outcome: str,
    home_player: str,
    away_player: str,
) -> str:
    if typename in {"12", "HT", "HT1", "HT2"}:
        if outcome == "1":
            return home_player
        if outcome in {"2", "3"}:
            return away_player
    if typename in {"OU", "OUJ"}:
        return {"2": "Under", "3": "Over"}.get(outcome, outcome)
    if typename == "BTTS":
        return {"1": "Oui", "2": "Non"}.get(outcome, outcome)
    if typename == "EXACT":
        if re.fullmatch(r"\d-\d", outcome):
            left, right = outcome.split("-", 1)
            if int(left) > int(right):
                return f"{home_player} {left}:{right}"
            return f"{away_player} {right}:{left}"
        if ":" in outcome:
            return outcome
        if "-" in outcome:
            return outcome.replace("-", ":")
        return outcome
    return outcome


def map_coteur_to_fanduel(typename: str, special: str) -> str | None:
    if typename in COTEUR_EXCLUDED_TYPES:
        return None
    base = COTEUR_TO_FANDUEL_BASE.get(typename)
    if base is None:
        return None
    if typename == "12" and special:
        line = coteur_handicap_line(special)
        if line is not None:
            return f"set_handicap|{line}"
        return None
    line = coteur_special_line(typename, special)
    if line not in (None, "") and base in {"totals", "total_sets", "set_totals"}:
        return f"{base}|{line}"
    return base


def format_numeric_line(value: str | float | int) -> str:
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return str(number)


def extract_total_line_from_market_name(name: str) -> str | None:
    matches = re.findall(r"(\d+(?:\.\d+)?)", name)
    if not matches:
        return None
    value = matches[-1]
    try:
        return format_numeric_line(value)
    except ValueError:
        return value


def extract_line_from_runner_names(market: dict[str, Any]) -> str | None:
    for runner in market.get("runners", []):
        runner_name = str(runner.get("runnerName", ""))
        matches = re.findall(r"\(([+-]?\d+(?:\.\d+)?)\)", runner_name)
        if matches:
            try:
                return format_numeric_line(abs(float(matches[-1])))
            except ValueError:
                continue
    return None


def _book_player_key(name: str) -> str:
    tokens = player_tokens(name)
    if not tokens:
        return normalize_player(name)
    parts = re.split(r"[\s.]+", _strip_accents(name))
    parts = [part for part in parts if len(part) >= 3]
    if parts and parts[-1] in tokens:
        return parts[-1]
    return max(tokens, key=len)


def _strip_accents(value: str) -> str:
    return (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def map_fanduel_market_to_compare_key(market: dict[str, Any]) -> str | None:
    name = str(market.get("marketName", "")).strip()
    lower = name.lower()
    if lower in {"moneyline", "match betting"}:
        return "h2h"
    if lower == "set 1 winner":
        return "set1_winner"
    if lower == "set 2 winner":
        return "set2_winner"
    if lower == "set betting":
        return "set_betting"
    if lower.startswith("total match games"):
        line = extract_total_line_from_market_name(name)
        return f"totals|{line}" if line else None
    if lower.startswith("total sets"):
        line = extract_total_line_from_market_name(name)
        return f"total_sets|{line}" if line else None
    if lower == "both players to win a set (yes/no)":
        return "both_win_set"
    if lower.startswith("alternative total sets"):
        line = extract_line_from_runner_names(market)
        return f"total_sets|{line}" if line else None
    if "set handicap" in lower:
        line = extract_total_line_from_market_name(name) or extract_line_from_runner_names(market)
        return f"set_handicap|{line}" if line else None
    if "game handicap" in lower or lower.startswith("handicap"):
        line = extract_total_line_from_market_name(name) or extract_line_from_runner_names(market)
        return f"game_handicap|{line}" if line else None
    if re.search(r"set 1 total games", lower):
        line = extract_total_line_from_market_name(name)
        return f"set1_totals|{line}" if line else None
    if re.search(r"set 2 total games", lower):
        line = extract_total_line_from_market_name(name)
        return f"set2_totals|{line}" if line else None
    return None


def fanduel_runner_label(
    compare_key: str,
    runner_name: str,
    home_player: str,
    away_player: str,
) -> str:
    name = runner_name.strip()
    lower = name.lower()
    if compare_key == "h2h":
        return name
    if compare_key in {"set1_winner", "set2_winner"}:
        return name
    if compare_key == "set_betting":
        score_match = re.search(r"(\d-\d)$", name)
        if score_match:
            score = score_match.group(1).replace("-", ":")
            player_part = name[: score_match.start()].strip()
            if normalize_player(player_part) == normalize_player(home_player):
                return f"{home_player} {score}"
            if normalize_player(player_part) == normalize_player(away_player):
                return f"{away_player} {score}"
        return name.replace(" ", "")
    if compare_key.startswith("set_handicap|") or compare_key.startswith("game_handicap|"):
        if "(" in name and ")" in name:
            return name
        if lower == "handicap draw":
            return "Handicap Draw"
        return name
    if compare_key.startswith("totals") or compare_key.startswith("set") and "totals" in compare_key:
        if lower.startswith("over"):
            return "Over"
        if lower.startswith("under"):
            return "Under"
    if compare_key.startswith("total_sets|"):
        if lower.startswith("over"):
            return "Over"
        if lower.startswith("under"):
            return "Under"
    if compare_key == "both_win_set":
        if lower == "yes" or lower.endswith(" yes"):
            return "Oui"
        if lower == "no" or lower.endswith(" no"):
            return "Non"
    return name


def map_fanduel_aces_market_to_compare_key(
    market: dict[str, Any],
    home_player: str,
    away_player: str,
) -> str | None:
    name = str(market.get("marketName", "")).strip()
    lower = name.lower()
    line = extract_total_line_from_market_name(name)

    if re.fullmatch(r"total aces [\d.]+", lower) and line:
        return f"aces_total|{line}"
    player_total = re.match(r"^total (.+?) aces [\d.]+$", name, flags=re.I)
    if player_total and line:
        player_name = player_total.group(1).strip()
        if players_match(player_name, home_player):
            player_token = _book_player_key(home_player)
        elif players_match(player_name, away_player):
            player_token = _book_player_key(away_player)
        else:
            player_token = _book_player_key(player_name)
        return f"aces_player|{player_token}|{line}"
    if lower == "total aces in the match":
        return "aces_total_tiers"
    if lower.endswith(" aces") and "total" not in lower and not lower.startswith("set "):
        player_name = name[: -len(" Aces")].strip()
        if players_match(player_name, home_player):
            player_token = _book_player_key(home_player)
        elif players_match(player_name, away_player):
            player_token = _book_player_key(away_player)
        else:
            player_token = _book_player_key(player_name)
        return f"aces_player_tiers|{player_token}"
    if re.match(r"^set \d+ aces$", lower):
        set_number = re.search(r"set (\d+)", lower)
        return f"aces_set_tiers|{set_number.group(1) if set_number else '1'}"
    return None


def fanduel_aces_runner_outcome(
    market: dict[str, Any],
    runner_name: str,
    compare_key: str | None,
) -> str:
    name = runner_name.strip()
    lower = name.lower()
    if compare_key and compare_key.startswith(("aces_total|", "aces_player|")):
        if lower.startswith("over"):
            return "Over"
        if lower.startswith("under"):
            return "Under"
    if lower == "zero":
        return "0+"
    tier = re.match(r"(\d+)\+", lower)
    if tier:
        return f"{tier.group(1)}+"
    return name


def fr_compare_key_to_fanduel(compare_key: str) -> str:
    if compare_key.startswith("games_total|"):
        return compare_key.replace("games_total|", "totals|", 1)
    return compare_key


def fanduel_compare_key_to_fr(compare_key: str) -> str:
    if compare_key.startswith("totals|"):
        return compare_key.replace("totals|", "games_total|", 1)
    return compare_key


def align_fr_outcome_to_fanduel(
    outcome: str,
    compare_key: str,
    home_player: str,
    away_player: str,
) -> str:
    family = compare_key.split("|", 1)[0]
    if family in {"h2h", "set1_winner", "set2_winner", "first_break"}:
        if players_match(outcome, home_player):
            return home_player
        if players_match(outcome, away_player):
            return away_player
    if family in {"games_total", "totals", "total_sets", "breaks_total", "aces_total", "tie_break_match"}:
        lower = outcome.lower()
        if lower in {"over", "under"}:
            return outcome.capitalize()
        if lower.startswith("plus"):
            return "Over"
        if lower.startswith("moins"):
            return "Under"
    if family == "aces_player":
        lower = outcome.lower()
        if lower.startswith("plus"):
            return "Over"
        if lower.startswith("moins"):
            return "Under"
    if family == "both_win_set":
        return {"Oui": "Oui", "Non": "Non", "Yes": "Oui", "No": "Non"}.get(outcome, outcome)
    return outcome
