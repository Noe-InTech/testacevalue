"""Mapping Bet365 US → cles compare (iso FanDuel / FR)."""

from __future__ import annotations

import re
from typing import Any

from fanduel_client import american_to_decimal_fr, decimal_fr_to_american
from tennis_market_mapping import (
    _book_player_key,
    extract_total_line_from_market_name,
    format_numeric_line,
    players_match,
)


def _price_bundle(*, american: int | float | None = None, decimal: float | None = None) -> dict[str, Any] | None:
    dec = decimal
    am = american
    if dec is None and am is not None:
        dec = american_to_decimal_fr(am)
    if am is None and dec is not None:
        am = decimal_fr_to_american(dec)
    if dec is None:
        return None
    return {
        "american": am,
        "decimal_raw": float(dec),
        "decimal_fr": float(dec),
    }


def runner_outcome_ou(runner_name: str) -> str | None:
    lower = runner_name.strip().lower()
    if lower.startswith(("over", "plus", "o ")) or lower in {"o", "over"}:
        return "Over"
    if lower.startswith(("under", "moins", "u ")) or lower in {"u", "under"}:
        return "Under"
    if lower in {"yes", "oui"}:
        return "Yes"
    if lower in {"no", "non"}:
        return "No"
    # "Player Name Over 3.5" / "Over 3.5"
    if re.search(r"\bover\b", lower):
        return "Over"
    if re.search(r"\bunder\b", lower):
        return "Under"
    return None


def map_bet365_tennis_market_to_compare_key(
    market_name: str,
    home_player: str,
    away_player: str,
) -> str | None:
    name = market_name.strip()
    lower = name.lower()
    line = extract_total_line_from_market_name(name)

    # Total match aces O/U
    if line and re.fullmatch(r"(total )?aces( of the match| in the match)? [\d.]+", lower):
        return f"aces_total|{format_numeric_line(line)}"
    if line and re.fullmatch(r"total aces [\d.]+", lower):
        return f"aces_total|{format_numeric_line(line)}"

    # Player aces O/U — "Sinner Total Aces 8.5" / "Total Sinner Aces 8.5"
    player_aces = re.match(
        r"^(?:total\s+)?(.+?)\s+(?:total\s+)?aces\s+([\d.]+)$",
        name,
        flags=re.I,
    )
    if player_aces:
        player_name = player_aces.group(1).strip()
        line_s = format_numeric_line(float(player_aces.group(2)))
        if players_match(player_name, home_player):
            token = _book_player_key(home_player)
        elif players_match(player_name, away_player):
            token = _book_player_key(away_player)
        else:
            token = _book_player_key(player_name)
        return f"aces_player|{token}|{line_s}"

    # Total breaks
    if line and re.fullmatch(r"(total )?breaks( of serve)?( in the match)? [\d.]+", lower):
        return f"breaks_total|{format_numeric_line(line)}"
    if line and re.fullmatch(r"total breaks [\d.]+", lower):
        return f"breaks_total|{format_numeric_line(line)}"

    player_breaks = re.match(
        r"^(?:total\s+)?(.+?)\s+(?:total\s+)?breaks(?:\s+of\s+serve)?\s+([\d.]+)$",
        name,
        flags=re.I,
    )
    if player_breaks:
        player_name = player_breaks.group(1).strip()
        line_s = format_numeric_line(float(player_breaks.group(2)))
        if players_match(player_name, home_player):
            token = _book_player_key(home_player)
        elif players_match(player_name, away_player):
            token = _book_player_key(away_player)
        else:
            token = _book_player_key(player_name)
        return f"breaks_player|{token}|{line_s}"

    if line and re.fullmatch(r"total tie ?breaks? [\d.]+", lower):
        return f"tie_break_match|{format_numeric_line(line)}"

    if re.fullmatch(r"service break number 1|first service break|to break first", lower):
        return "first_break"

    set_tie = re.match(r"^(?:tie ?break in )?set (\d+)(?: tie ?break)?$", lower)
    if set_tie and "tie" in lower:
        return f"tie_break_set|{set_tie.group(1)}"

    return None


def map_bet365_basketball_market_to_compare_key(
    market_name: str,
    player_hint: str = "",
    roster: list[str] | None = None,
) -> str | None:
    """Mappe props joueur WNBA/NBA via les memes specs FanDuel."""
    from basketball_market_mapping import map_fanduel_market_to_compare_key

    name = market_name.strip()
    if player_hint and player_hint.lower() not in name.lower():
        name = f"{player_hint} {name}"
    return map_fanduel_market_to_compare_key({"marketName": name}, roster=roster)


def map_bet365_baseball_market_to_compare_key(
    market_name: str,
    *,
    home_team: str = "",
    away_team: str = "",
    player_hint: str = "",
) -> str | None:
    from baseball_market_mapping import (
        build_hits_player_key,
        build_runs_player_key,
        build_strikeouts_pitcher_key,
        build_total_bases_player_key,
    )

    name = market_name.strip()
    lower = name.lower()
    line_match = re.search(r"([\d.]+)\s*$", name)
    line = float(line_match.group(1)) if line_match else None
    player = player_hint
    if not player:
        m = re.match(
            r"^(.+?)\s+(to score a run|runs|hits|total bases|strikeouts|pitcher strikeouts)\b",
            name,
            re.I,
        )
        if m:
            player = m.group(1).strip()

    if "to score a run" in lower or re.search(r"\bruns?\b", lower) and "team" not in lower:
        if player and (line is None or line in {0.5, 1, 1.0}):
            return build_runs_player_key(player, 1)
    if player and line is not None:
        if "strikeout" in lower:
            return build_strikeouts_pitcher_key(player, line)
        if "total bases" in lower:
            return build_total_bases_player_key(player, line)
        if re.search(r"\bhits?\b", lower):
            return build_hits_player_key(player, line)
    return None


def build_normalized_map_from_bet365_markets(
    markets: list[dict[str, Any]],
    *,
    sport: str,
    home: str,
    away: str,
    families: set[str] | None = None,
    captured_at: str = "",
) -> dict[str, dict[str, Any]]:
    """
    markets items:
      {
        "market_name": str,
        "player_name": optional str,
        "runners": [{"name": str, "american": int?} | {"name": str, "decimal": float?}]
      }
    """
    sport_key = sport.strip().lower()
    variant_map: dict[str, dict[str, Any]] = {}

    for market in markets:
        label = str(market.get("market_name") or market.get("marketName") or "").strip()
        if not label:
            continue
        player_hint = str(market.get("player_name") or "").strip()

        compare_key: str | None = None
        market_family = ""
        if sport_key == "tennis":
            compare_key = map_bet365_tennis_market_to_compare_key(label, home, away)
            if compare_key:
                market_family = compare_key.split("|", 1)[0]
        elif sport_key in {"wnba", "nba"}:
            compare_key = map_bet365_basketball_market_to_compare_key(label, player_hint)
            if compare_key:
                market_family = compare_key.split("|", 1)[0]
        elif sport_key == "baseball":
            compare_key = map_bet365_baseball_market_to_compare_key(
                label,
                home_team=home,
                away_team=away,
                player_hint=player_hint,
            )
            if compare_key:
                market_family = compare_key.split("|", 1)[0]
        else:
            continue

        if not compare_key:
            continue
        if families and market_family not in families and not any(
            compare_key.startswith(f"{f}|") or compare_key == f for f in families
        ):
            # families may be high-level: aces, breaks, props…
            family_groups = {
                "aces": ("aces_total", "aces_player", "aces_total_tiers", "aces_player_tiers"),
                "breaks": (
                    "breaks_total",
                    "breaks_player",
                    "tie_break_match",
                    "tie_break_set",
                    "first_break",
                ),
                "victoires": ("match_winner", "moneyline"),
            }
            allowed: set[str] = set()
            for item in families:
                allowed.add(item)
                allowed.update(family_groups.get(item, ()))
            if market_family not in allowed and compare_key not in allowed:
                continue

        outcomes: dict[str, dict[str, Any]] = {}
        for runner in market.get("runners") or []:
            runner_name = str(runner.get("name") or runner.get("runnerName") or "").strip()
            if not runner_name:
                continue
            aligned = runner_outcome_ou(runner_name)
            if compare_key == "first_break":
                aligned = runner_name
            elif compare_key.startswith("tie_break_set|"):
                raw = runner_outcome_ou(runner_name)
                if raw == "Yes":
                    aligned = "Oui"
                elif raw == "No":
                    aligned = "Non"
                else:
                    aligned = raw
            if not aligned:
                continue
            bundle = _price_bundle(
                american=runner.get("american"),
                decimal=runner.get("decimal") or runner.get("decimal_fr"),
            )
            if not bundle:
                continue
            outcomes[aligned] = bundle

        if not outcomes:
            continue

        player_name = player_hint
        if sport_key == "tennis" and compare_key.startswith(("aces_player|", "breaks_player|")):
            parts = compare_key.split("|")
            if len(parts) >= 2:
                player_name = parts[1].replace("_", " ")
        elif sport_key in {"wnba", "nba", "baseball"} and "|" in compare_key:
            parts = compare_key.split("|")
            if len(parts) >= 2 and parts[1] not in {"home", "away"}:
                player_name = parts[1].replace("_", " ")

        variant_map[compare_key] = {
            "compare_key": compare_key,
            "market_label": label,
            "market_label_raw": label,
            "market_family": market_family,
            "player_name": player_name,
            "fd_line_source": "ou",
            "captured_at": captured_at,
            "outcomes": outcomes,
        }

    return variant_map
