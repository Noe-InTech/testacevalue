"""Clés canoniques et alignement baseball (FR ↔ FanDuel)."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from baseball_constants import COMPARABLE_FAMILIES
from tennis_market_mapping import format_numeric_line, players_match


def strip_accents(value: str) -> str:
    return (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def team_token(name: str) -> str:
    parts = re.split(r"[\s.\-/]+", strip_accents(name))
    parts = [part for part in parts if part and part not in {"vs", "v", "at", "the"}]
    if not parts:
        return "team"
    # Prefer distinctive nickname (last token) for MLB-style names.
    return parts[-1]


def player_token(name: str) -> str:
    text = normalize_person_name(name)
    parts = re.split(r"[\s.]+", strip_accents(text))
    parts = [part for part in parts if part]
    if not parts:
        return "player"
    if len(parts) >= 2 and all(len(part) == 1 for part in parts[:-1]):
        return parts[-1]
    return parts[-1]


def normalize_person_name(name: str) -> str:
    """Normalize ``Last, First`` (Unibet) to ``First Last``."""
    text = str(name or "").strip()
    if "," not in text:
        return text
    last, first = [part.strip() for part in text.split(",", 1)]
    if last and first:
        return f"{first} {last}".strip()
    return text


def resolve_roster_player(name: str, roster: list[str]) -> str:
    text = normalize_person_name(str(name or "").strip())
    if not text:
        return text
    for candidate in roster:
        if players_match(text, candidate):
            return normalize_person_name(candidate)
    return text


def is_comparable_key(compare_key: str) -> bool:
    family = compare_key.split("|", 1)[0]
    return family in COMPARABLE_FAMILIES


def teams_match(home_a: str, away_a: str, home_b: str, away_b: str) -> bool:
    return (
        players_match(home_a, home_b) and players_match(away_a, away_b)
    ) or (
        players_match(home_a, away_b) and players_match(away_a, home_b)
    )


def resolve_team_side(label: str, home_team: str, away_team: str) -> str | None:
    text = str(label or "").strip()
    lower = strip_accents(text)
    if lower in {"n", "nul", "egalite", "égalité", "tie", "draw", "match nul", "x"}:
        return "draw"
    if players_match(text, home_team):
        return "home"
    if players_match(text, away_team):
        return "away"
    # Labels like "MIA Marlins Over" / "Philadelphia Phillies -1.5"
    cleaned = re.sub(
        r"\b(?:over|under|plus|moins|de)\b.*$",
        "",
        text,
        flags=re.I,
    ).strip()
    cleaned = re.sub(r"[\[\(]?[+\-]?\d+[.,]?\d*[\]\)]?\s*$", "", cleaned).strip()
    if cleaned and players_match(cleaned, home_team):
        return "home"
    if cleaned and players_match(cleaned, away_team):
        return "away"
    return None


def parse_signed_line(text: str) -> float | None:
    """Extract a betting line from a label, ignoring ordinals like 1st / 1er.

    Prefer parenthetical lines ``(0.5)`` and decimals ``8.5`` over the bare
    ``1`` in ``1st Inning`` / ``1er manche``.
    """
    raw = str(text or "")
    if not raw.strip():
        return None

    paren = re.search(r"\(([+\-]?\d+(?:[.,]\d+)?)\)", raw)
    if paren:
        try:
            return float(paren.group(1).replace(",", "."))
        except ValueError:
            pass

    decimals = list(re.finditer(r"[+\-]?\d+[.,]\d+", raw))
    if decimals:
        try:
            return float(decimals[-1].group(0).replace(",", "."))
        except ValueError:
            pass

    cleaned = re.sub(
        r"\b\d+(?:st|nd|rd|th|er|re|ere|ème|eme|e)\b",
        " ",
        raw,
        flags=re.I,
    )
    match = re.search(r"([+\-]?\d+(?:[.,]\d+)?)", cleaned)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def build_h2h_key() -> str:
    return "h2h"


def build_run_line_key(line: float | str) -> str:
    return f"run_line|{format_numeric_line(abs(float(line)))}"


def build_runs_total_key(line: float | str) -> str:
    return f"runs_total|{format_numeric_line(line)}"


def build_runs_team_key(team_name: str, line: float | str) -> str:
    return f"runs_team|{team_token(team_name)}|{format_numeric_line(line)}"


def build_f5_h2h_key() -> str:
    return "f5_h2h"


def build_f5_run_line_key(line: float | str) -> str:
    return f"f5_run_line|{format_numeric_line(abs(float(line)))}"


def build_f5_runs_total_key(line: float | str) -> str:
    return f"f5_runs_total|{format_numeric_line(line)}"


def build_inning1_result_key() -> str:
    return "inning1_result"


def build_inning1_runs_total_key(line: float | str) -> str:
    return f"inning1_runs_total|{format_numeric_line(line)}"


def build_hr_player_key(player_name: str, threshold: int | float | str = 1) -> str:
    token = player_token(player_name)
    thr = format_numeric_line(threshold)
    if thr in {"1", "1.0"}:
        return f"hr_player|{token}"
    return f"hr_player|{token}|{thr}"


def build_hits_player_key(player_name: str, threshold: int | float | str = 1) -> str:
    token = player_token(player_name)
    thr = format_numeric_line(threshold)
    if thr in {"1", "1.0"}:
        return f"hits_player|{token}"
    return f"hits_player|{token}|{thr}"


def build_rbi_player_key(player_name: str, threshold: int | float | str = 1) -> str:
    token = player_token(player_name)
    thr = format_numeric_line(threshold)
    if thr in {"1", "1.0"}:
        return f"rbi_player|{token}"
    return f"rbi_player|{token}|{thr}"


def build_total_bases_player_key(player_name: str, threshold: int | float | str) -> str:
    return f"total_bases_player|{player_token(player_name)}|{format_numeric_line(threshold)}"


def build_sb_player_key(player_name: str, threshold: int | float | str = 1) -> str:
    token = player_token(player_name)
    thr = format_numeric_line(threshold)
    if thr in {"1", "1.0"}:
        return f"sb_player|{token}"
    return f"sb_player|{token}|{thr}"


def build_runs_player_key(player_name: str, threshold: int | float | str) -> str:
    return f"runs_player|{player_token(player_name)}|{format_numeric_line(threshold)}"


def build_strikeouts_pitcher_key(player_name: str, line: float | str) -> str:
    return f"strikeouts_pitcher|{player_token(player_name)}|{format_numeric_line(line)}"


def fanduel_ou_outcome(runner_name: str) -> str | None:
    lower = strip_accents(runner_name)
    if "over" in lower or lower.endswith(" over"):
        return "Over"
    if "under" in lower or lower.endswith(" under"):
        return "Under"
    if lower in {"over", "under"}:
        return "Over" if lower == "over" else "Under"
    return None


def map_fanduel_market_to_entries(
    market: dict[str, Any],
    *,
    home_team: str,
    away_team: str,
    roster: list[str],
) -> list[tuple[str, str, str, dict[str, Any]]]:
    """Retourne (compare_key, outcome, market_label, runner) pour chaque sélection comparable."""
    market_label = str(market.get("marketName") or market.get("name") or "")
    market_type = str(market.get("marketType") or "")
    lower = strip_accents(market_label)
    entries: list[tuple[str, str, str, dict[str, Any]]] = []

    runners = [
        runner
        for runner in (market.get("runners") or [])
        if runner.get("runnerStatus") in (None, "ACTIVE")
    ]
    if not runners:
        return entries

    # SGP / parlay wrappers (e.g. "First 5 Innings Run Line / Total Runs Parlay")
    # are not 1:1 comparable to FR straight markets.
    if "parlay" in lower or "sgp" in lower or "same game" in lower:
        return entries

    def add(compare_key: str, outcome: str, runner: dict[str, Any]) -> None:
        if compare_key and outcome:
            entries.append((compare_key, outcome, market_label, runner))

    # Moneyline
    if market_type == "MONEY_LINE" or lower == "moneyline":
        for runner in runners:
            side = resolve_team_side(str(runner.get("runnerName", "")), home_team, away_team)
            if side in {"home", "away"}:
                add(build_h2h_key(), side, runner)
        return entries

    # Run line (main + alternate)
    if market_type in {"MATCH_HANDICAP_(2-WAY)", "ALTERNATE_RUN_LINES"} or lower in {
        "run line",
        "alternate run lines",
    }:
        for runner in runners:
            runner_name = str(runner.get("runnerName", ""))
            handicap = runner.get("handicap")
            if handicap in (None, "", 0, 0.0) and re.search(r"[+\-]\d", runner_name):
                handicap = parse_signed_line(runner_name)
            if handicap is None:
                continue
            side = resolve_team_side(runner_name, home_team, away_team)
            if side in {"home", "away"}:
                add(build_run_line_key(float(handicap)), side, runner)
        return entries

    # Total runs (main + alternate)
    if market_type in {"TOTAL_POINTS_(OVER/UNDER)", "ALTERNATE_TOTAL_RUNS"} or lower in {
        "total runs",
        "alternate total runs",
    }:
        for runner in runners:
            runner_name = str(runner.get("runnerName", ""))
            handicap = runner.get("handicap")
            if handicap in (None, "", 0, 0.0):
                handicap = parse_signed_line(runner_name)
            outcome = fanduel_ou_outcome(runner_name)
            if handicap is None or outcome is None:
                # Alternate: "Over 8.5"
                m = re.match(r"(over|under)\s+([\d.]+)", strip_accents(runner_name), flags=re.I)
                if not m:
                    continue
                outcome = "Over" if m.group(1) == "over" else "Under"
                handicap = float(m.group(2))
            add(build_runs_total_key(float(handicap)), outcome, runner)
        return entries

    # Team totals
    if market_type in {"HOME_TOTAL_RUNS", "AWAY_TOTAL_RUNS"} or (
        "total runs" in lower and (players_match(market_label, home_team) or players_match(market_label, away_team))
    ):
        team = home_team if market_type == "HOME_TOTAL_RUNS" or players_match(market_label, home_team) else away_team
        if market_type == "AWAY_TOTAL_RUNS":
            team = away_team
        for runner in runners:
            runner_name = str(runner.get("runnerName", ""))
            handicap = runner.get("handicap")
            if handicap in (None, "", 0, 0.0):
                handicap = parse_signed_line(runner_name)
            outcome = fanduel_ou_outcome(runner_name)
            if handicap is None or outcome is None:
                continue
            add(build_runs_team_key(team, float(handicap)), outcome, runner)
        return entries

    # First 5 innings
    if "first 5 innings money line" in lower or market_type == "1ST_HALF_MONEY_LINE":
        for runner in runners:
            side = resolve_team_side(str(runner.get("runnerName", "")), home_team, away_team)
            if side in {"home", "away"}:
                add(build_f5_h2h_key(), side, runner)
        return entries

    if (
        market_type == "1ST_HALF_RUN_LINE"
        or lower == "first 5 innings run line"
        or (lower.startswith("first 5 innings run line") and "total" not in lower)
    ):
        for runner in runners:
            runner_name = str(runner.get("runnerName", ""))
            handicap = runner.get("handicap")
            if handicap in (None, "", 0, 0.0):
                handicap = parse_signed_line(runner_name)
            side = resolve_team_side(runner_name, home_team, away_team)
            if side in {"home", "away"} and handicap is not None:
                add(build_f5_run_line_key(float(handicap)), side, runner)
        return entries

    if (
        market_type == "1ST_HALF_TOTAL_RUNS"
        or lower == "first 5 innings total runs"
        or (lower.startswith("first 5 innings total runs") and "run line" not in lower)
    ):
        for runner in runners:
            runner_name = str(runner.get("runnerName", ""))
            handicap = runner.get("handicap")
            if handicap in (None, "", 0, 0.0):
                handicap = parse_signed_line(runner_name)
            outcome = fanduel_ou_outcome(runner_name)
            if handicap is None or outcome is None:
                continue
            add(build_f5_runs_total_key(float(handicap)), outcome, runner)
        return entries

    # 1st inning
    if lower in {"1st inning result"} or market_type == "1ST_INNING_RESULT":
        for runner in runners:
            side = resolve_team_side(str(runner.get("runnerName", "")), home_team, away_team)
            if side:
                add(build_inning1_result_key(), side, runner)
        return entries

    if "1st inning" in lower and (
        "over/under" in lower or "total runs" in lower or "runs" in lower
    ):
        for runner in runners:
            runner_name = str(runner.get("runnerName", ""))
            handicap = runner.get("handicap")
            if handicap in (None, "", 0, 0.0):
                handicap = parse_signed_line(market_label) or parse_signed_line(runner_name)
            outcome = fanduel_ou_outcome(runner_name)
            if handicap is None or outcome is None:
                continue
            add(build_inning1_runs_total_key(float(handicap)), outcome, runner)
        return entries

    # Batter HR yes / 2+
    if lower == "to hit a home run" or market_type == "TO_HIT_A_HOME_RUN":
        for runner in runners:
            player = resolve_roster_player(str(runner.get("runnerName", "")).strip(), roster)
            if player:
                add(build_hr_player_key(player, 1), "Yes", runner)
        return entries

    if lower == "to hit 2+ home runs" or market_type == "TO_HIT_2+_HOME_RUNS":
        for runner in runners:
            player = resolve_roster_player(str(runner.get("runnerName", "")).strip(), roster)
            if player:
                add(build_hr_player_key(player, 2), "Yes", runner)
        return entries

    # Batter runs yes / 2+
    if lower in {"to record a run", "to record 2+ runs"} or market_type in {
        "TO_RECORD_A_RUN",
        "TO_RECORD_2+_RUNS",
    }:
        threshold = 2 if "2+" in lower or "2+" in market_type else 1
        for runner in runners:
            player = resolve_roster_player(str(runner.get("runnerName", "")).strip(), roster)
            if player:
                add(build_runs_player_key(player, threshold), "Yes", runner)
        return entries

    # Hits yes / 2+
    if lower in {"to record a hit", "to record 2+ hits"} or market_type in {
        "PLAYER_TO_RECORD_A_HIT",
        "PLAYER_TO_RECORD_2+_HITS",
    }:
        threshold = 2 if "2+" in lower or "2+" in market_type else 1
        for runner in runners:
            player = resolve_roster_player(str(runner.get("runnerName", "")).strip(), roster)
            if player:
                add(build_hits_player_key(player, threshold), "Yes", runner)
        return entries

    # RBI yes / 2+
    if lower in {"to record an rbi", "to record 2+ rbis"} or market_type in {
        "TO_RECORD_AN_RBI",
        "TO_RECORD_2+_RBIS",
    }:
        threshold = 2 if "2+" in lower or "2+" in market_type else 1
        for runner in runners:
            player = resolve_roster_player(str(runner.get("runnerName", "")).strip(), roster)
            if player:
                add(build_rbi_player_key(player, threshold), "Yes", runner)
        return entries

    # Total bases N+
    tb_match = re.match(r"to record (\d+)\+ total bases$", lower)
    if tb_match or "TOTAL_BASES" in market_type:
        threshold = int(tb_match.group(1)) if tb_match else None
        if threshold is None:
            m = re.search(r"(\d+)\+", lower)
            threshold = int(m.group(1)) if m else None
        if threshold is not None:
            for runner in runners:
                player = resolve_roster_player(str(runner.get("runnerName", "")).strip(), roster)
                if player:
                    add(build_total_bases_player_key(player, threshold), "Yes", runner)
            return entries

    # Stolen bases yes / 2+
    if lower in {"to record a stolen base", "to record 2+ stolen bases"} or market_type in {
        "TO_RECORD_A_STOLEN_BASE",
        "TO_RECORD_2+_STOLEN_BASES",
    }:
        threshold = 2 if "2+" in lower or "2+" in market_type else 1
        for runner in runners:
            player = resolve_roster_player(str(runner.get("runnerName", "")).strip(), roster)
            if player:
                add(build_sb_player_key(player, threshold), "Yes", runner)
        return entries

    # Pitcher strikeouts O/U
    strikeout_match = re.match(r"^(.+?)\s*-\s*strikeouts$", lower)
    if (
        strikeout_match
        or "TOTAL_STRIKEOUTS" in market_type
        or market_type.endswith("_TOTAL_STRIKEOUTS")
    ):
        player_raw = market_label.split(" - ")[0].strip() if " - " in market_label else ""
        if not player_raw and strikeout_match:
            player_raw = strikeout_match.group(1).strip()
        player = resolve_roster_player(player_raw, roster) if player_raw else ""
        if player:
            for runner in runners:
                runner_name = str(runner.get("runnerName", ""))
                # Skip alt "N+ Strikeouts" ladders here — O/U only.
                if re.search(r"\d+\s*\+\s*strikeouts?", strip_accents(runner_name)):
                    continue
                handicap = runner.get("handicap")
                if handicap in (None, "", 0, 0.0):
                    handicap = parse_signed_line(runner_name)
                outcome = fanduel_ou_outcome(runner_name)
                if handicap is None or outcome is None:
                    continue
                add(build_strikeouts_pitcher_key(player, float(handicap)), outcome, runner)
        return entries

    return entries
