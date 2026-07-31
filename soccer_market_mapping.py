"""Mapping marchés foot FR / FanDuel → clés comparables."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from soccer_constants import COMPARABLE_FAMILIES, FAMILY_LABELS_FR
from tennis_market_mapping import player_tokens, players_match


def strip_accents(text: str) -> str:
    return (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def normalize_player_display(name: str) -> str:
    text = re.sub(r"\s+", " ", str(name or "")).strip()
    text = re.sub(r"\bJr\.?\b", "", text, flags=re.I).strip()
    return text


def player_token(name: str) -> str:
    """Token stable : initiale prénom + nom (évite collisions simples)."""
    cleaned = strip_accents(normalize_player_display(name)).lower()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    parts = [p for p in cleaned.split() if p and p not in {"jr", "junior"}]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0][0]}{parts[-1]}"


def resolve_roster_player(name: str, roster: list[str]) -> str:
    text = normalize_player_display(name)
    if not text:
        return ""
    for candidate in roster:
        if players_match(text, candidate) or player_token(text) == player_token(candidate):
            return candidate
    # fuzzy last-name equality
    tokens = player_tokens(text)
    for candidate in roster:
        other = player_tokens(candidate)
        if tokens & other:
            return candidate
    return text


def build_yes_player_key(family: str, player_name: str) -> str | None:
    if family not in COMPARABLE_FAMILIES:
        return None
    token = player_token(player_name)
    if not token:
        return None
    return f"{family}|{token}|yes"


def build_tier_player_key(family: str, player_name: str, threshold: int) -> str | None:
    if family not in COMPARABLE_FAMILIES:
        return None
    token = player_token(player_name)
    if not token or threshold < 1:
        return None
    return f"{family}|{token}|{threshold}+"


def is_comparable_soccer_key(compare_key: str) -> bool:
    family = compare_key.split("|", 1)[0] if compare_key else ""
    return family in COMPARABLE_FAMILIES


def classify_fr_market_label(label: str) -> str | None:
    """Retourne la famille canonique ou None si hors scope / variantes SuperSub."""
    low = strip_accents(label).lower()
    # Exclusions: remplacant / extras / double chance / multi-buts
    if any(
        k in low
        for k in (
            "remplacant",
            "extra gains",
            "double chance",
            "2 fois",
            "3 fois",
            "supersub",
        )
    ):
        return None

    if "premier buteur" in low or "1er buteur" in low or "first goalscorer" in low:
        return "first_goalscorer"
    if re.search(r"\bbuteur\b", low) and "passeur" not in low and "decisif" not in low:
        # Exact anytime: "Buteur (t. rég)" etc.
        if "ou son" in low:
            return None
        return "anytime_goalscorer"
    if "passeur" in low and "buteur" not in low and "decisif" not in low:
        return "anytime_assist"
    if "decisif" in low or ("buteur" in low and "passeur" in low):
        return "score_or_assist"
    if "carton" in low or "avertissement" in low:
        return "player_card"
    if "tirs cadres" in low or "tir cadre" in low:
        return "shots_on_target_player"
    if re.search(r"\btirs?\b", low) and "cadre" not in low:
        return "shots_player"
    if "corner" in low:
        return "corners_match"
    return None


def map_fanduel_soccer_market(
    market: dict[str, Any],
    *,
    roster: list[str],
) -> list[tuple[str, str, str, str, str]]:
    """Yield (compare_key, family, player_name, outcome, runner_name)."""
    label = str(market.get("marketName") or "").strip()
    low = label.lower()
    family: str | None = None
    outcome = "Yes"
    tier: int | None = None

    if label == "Anytime Goalscorer":
        family = "anytime_goalscorer"
    elif label == "First Goalscorer":
        family = "first_goalscorer"
    elif label == "To Score Or Assist":
        family = "score_or_assist"
    elif label == "Anytime Assist":
        family = "anytime_assist"
    elif "player to have" in low and "shots on target" in low:
        family = "shots_on_target_player"
        m = re.search(r"(\d+)\s+or more", low)
        tier = int(m.group(1)) if m else 1
    elif "player to have" in low and "shot" in low:
        family = "shots_player"
        m = re.search(r"(\d+)\s+or more", low)
        tier = int(m.group(1)) if m else 1
    elif "to be carded" in low or "player card" in low or "yellow card" in low:
        family = "player_card"
    elif "total corners" in low and "away" not in low and "home" not in low:
        return []

    if not family:
        return []

    results: list[tuple[str, str, str, str, str]] = []
    for runner in market.get("runners") or []:
        runner_name = str(runner.get("runnerName") or "").strip()
        if not runner_name:
            continue
        if runner_name.lower() in {"yes", "no", "over", "under"}:
            continue
        player = resolve_roster_player(runner_name, roster)
        if tier is not None:
            key = build_tier_player_key(family, player, tier)
        else:
            key = build_yes_player_key(family, player)
        if not key:
            continue
        results.append((key, family, player, outcome, runner_name))
    return results


def format_soccer_ligne(*, family: str, player_name: str, outcome: str, compare_key: str) -> str:
    label = FAMILY_LABELS_FR.get(family, family)
    issue = "Oui" if outcome in {"Yes", "Oui", "yes"} else outcome
    parts = compare_key.split("|")
    if len(parts) >= 3 and parts[2] not in {"yes", "no"}:
        return f"{issue} {parts[2]} {label} — {player_name}".strip(" —")
    if player_name:
        return f"{issue} {label} — {player_name}"
    return f"{issue} {label}"
