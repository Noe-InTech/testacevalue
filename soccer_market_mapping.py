"""Mapping marchés foot FR / FanDuel → clés comparables."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from soccer_constants import COMPARABLE_FAMILIES, FAMILY_LABELS_FR
from tennis_market_mapping import format_numeric_line, players_match


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
    cleaned = strip_accents(normalize_player_display(name)).lower()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    parts = [p for p in cleaned.split() if p and p not in {"jr", "junior"}]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0][0]}{parts[-1]}"


def team_token(name: str) -> str:
    parts = re.split(r"[\s.\-/]+", strip_accents(name).lower())
    parts = [p for p in parts if p and p not in {"vs", "v", "at", "the", "fc", "cf", "sc"}]
    if not parts:
        return "team"
    return parts[-1]


SOCCER_TEAM_STOPWORDS = {
    "fc",
    "cf",
    "sc",
    "ac",
    "afc",
    "sfc",
    "fk",
    "nk",
    "sk",
    "bk",
    "if",
    "club",
    "united",
    "city",
    "town",
    "athletic",
    "atletico",
    "sporting",
    "calcio",
    "de",
    "the",
    "vs",
    "v",
    "at",
    "w",
    "wfc",
    "women",
}


def soccer_team_tokens(name: str) -> set[str]:
    cleaned = strip_accents(normalize_player_display(name)).lower()
    cleaned = re.sub(r"\([^)]*\)", " ", cleaned)
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    tokens = {t for t in cleaned.split() if t and t not in SOCCER_TEAM_STOPWORDS and len(t) >= 3}
    return tokens


def soccer_team_match(name_a: str, name_b: str) -> bool:
    """Appariement clubs strict — évite les faux positifs City/FC."""
    a = strip_accents(normalize_player_display(name_a)).lower().strip()
    b = strip_accents(normalize_player_display(name_b)).lower().strip()
    if not a or not b:
        return False
    if a == b:
        return True
    if (a in b or b in a) and min(len(a), len(b)) >= 8:
        # still reject pure stopword-only containment like "fc" in "xyz fc"
        ta, tb = soccer_team_tokens(name_a), soccer_team_tokens(name_b)
        if ta and tb and (ta <= tb or tb <= ta):
            shorter, longer = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
            extra = longer - shorter
            if not extra or all(len(t) <= 3 for t in extra):
                return True
            # one strong shared base (e.g. philadelphia ⊂ philadelphia union)
            if any(len(t) >= 6 for t in shorter) and len(extra) <= 1:
                return True
            return False
        if not ta and not tb:
            return True
    ta, tb = soccer_team_tokens(name_a), soccer_team_tokens(name_b)
    if not ta or not tb:
        return False
    if ta == tb:
        return True
    shorter, longer = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if shorter <= longer:
        extra = longer - shorter
        if not extra or all(len(t) <= 3 for t in extra):
            return True
        if any(len(t) >= 6 for t in shorter) and len(extra) <= 1:
            return True
    shared = ta & tb
    if not shared:
        return False
    # Require almost-full coverage of the smaller set via strong tokens
    if shorter <= shared or (any(len(t) >= 6 for t in shared) and len(shared) == len(shorter)):
        extra = longer - shorter
        if len(extra) <= 1 or all(len(t) <= 3 for t in extra):
            return True
    return False


def soccer_teams_match(home_a: str, away_a: str, home_b: str, away_b: str) -> bool:
    return (
        soccer_team_match(home_a, home_b) and soccer_team_match(away_a, away_b)
    ) or (
        soccer_team_match(home_a, away_b) and soccer_team_match(away_a, home_b)
    )


def resolve_roster_player(name: str, roster: list[str]) -> str:
    text = normalize_player_display(name)
    if not text:
        return ""
    for candidate in roster:
        if players_match(text, candidate) or player_token(text) == player_token(candidate):
            return candidate
    from tennis_market_mapping import player_tokens

    tokens = player_tokens(text)
    for candidate in roster:
        other = player_tokens(candidate)
        if tokens & other:
            return candidate
    return text


def resolve_team_name(name: str, home: str, away: str) -> str:
    text = normalize_player_display(name)
    low = strip_accents(text).lower()
    if low in {"home", "domicile", "1"}:
        return home or text
    if low in {"away", "exterieur", "extérieur", "2"}:
        return away or text
    if home and soccer_team_match(text, home):
        return home
    if away and soccer_team_match(text, away):
        return away
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


def build_tier_subject_key(family: str, subject: str, threshold: int) -> str | None:
    if family not in COMPARABLE_FAMILIES:
        return None
    token = "match" if subject == "match" else team_token(subject)
    if not token or threshold < 1:
        return None
    return f"{family}|{token}|{threshold}+"


def build_ou_subject_key(family: str, subject: str, line: float | str) -> str | None:
    if family not in COMPARABLE_FAMILIES:
        return None
    token = "match" if subject == "match" else team_token(subject)
    if not token:
        return None
    return f"{family}|{token}|{format_numeric_line(line)}"


def is_comparable_soccer_key(compare_key: str) -> bool:
    family = compare_key.split("|", 1)[0] if compare_key else ""
    return family in COMPARABLE_FAMILIES


def classify_fr_market_label(label: str) -> str | None:
    """Retourne la famille canonique ou None si hors scope / variantes SuperSub."""
    low = strip_accents(label).lower()
    if any(
        k in low
        for k in (
            "remplacant",
            "extra gains",
            "double chance",
            "triple chance",
            "2 fois",
            "3 fois",
            "4 fois",
            "supersub",
            "duo buteur",
            "trio buteur",
            "face a face",
            "serial player",
            "dernier buteur",
            "mi-temps",
            "2de mi-temps",
            "dans les deux",
            "de 1'",
            "de 11'",
            "buteur de",
            "et son equipe",
        )
    ):
        return None

    if "premier buteur" in low or "1er buteur" in low or "first goalscorer" in low:
        return "first_goalscorer"
    if "joueur decisif" in low or "decisif (buteur" in low or (
        "buteur" in low and "passeur" in low
    ):
        return "score_or_assist"
    if "nombre de passes decisives" in low or (
        "passeur" in low and "buteur" not in low and "decisif" not in low
    ):
        return "anytime_assist"
    if re.search(r"\bbuteur\b", low) and "passeur" not in low and "decisif" not in low:
        if "ou son" in low:
            return None
        return "anytime_goalscorer"
    if "carton" in low or "avertissement" in low:
        return "player_card"

    # Match / team shots & corners before player shots
    if "corner" in low:
        if any(k in low for k in ("equipe", "team", "domicile", "exterieur", "home", "away")):
            return "corners_team"
        return "corners_match"
    if "tirs cadres" in low or "tir cadre" in low or "shots on target" in low:
        if any(k in low for k in ("match", "total", "nombre")) and "joueur" not in low:
            if any(k in low for k in ("equipe", "team", "domicile", "exterieur")):
                return "shots_on_target_team"
            return "shots_on_target_match"
        if "equipe" in low or "team" in low:
            return "shots_on_target_team"
        return "shots_on_target_player"
    if re.search(r"\btirs?\b", low) or "shots" in low:
        if "joueur" in low or "player" in low:
            return "shots_player"
        if any(k in low for k in ("equipe", "team", "domicile", "exterieur", "home", "away")):
            return "shots_team"
        if any(k in low for k in ("match", "total", "nombre")):
            return "shots_match"
        return "shots_player"
    return None


def _parse_plus_runner(name: str) -> tuple[str, int] | None:
    """'Nicolas Fernandez 1+' or '15 Or More Shots' → (subject, threshold)."""
    text = str(name or "").strip()
    m = re.match(r"^(.+?)\s+(\d+)\+\s*$", text)
    if m:
        return m.group(1).strip(), int(m.group(2))
    m = re.match(r"^(\d+)\s+or more(?:\s+shots)?$", text, flags=re.I)
    if m:
        return "match", int(m.group(1))
    return None


def map_fanduel_soccer_market(
    market: dict[str, Any],
    *,
    roster: list[str],
    home_team: str = "",
    away_team: str = "",
) -> list[tuple[str, str, str, str, str]]:
    """Yield (compare_key, family, subject_name, outcome, runner_name)."""
    label = str(market.get("marketName") or "").strip()
    low = label.lower()
    results: list[tuple[str, str, str, str, str]] = []

    def add(key: str | None, family: str, subject: str, outcome: str, runner_name: str) -> None:
        if key:
            results.append((key, family, subject, outcome, runner_name))

    # --- Player yes boards ---
    family_yes: str | None = None
    if label == "Anytime Goalscorer":
        family_yes = "anytime_goalscorer"
    elif label == "First Goalscorer":
        family_yes = "first_goalscorer"
    elif label == "To Score Or Assist":
        family_yes = "score_or_assist"
    elif label == "Anytime Assist":
        family_yes = "anytime_assist"
    elif "to be carded" in low or label == "Player Carded":
        family_yes = "player_card"

    if family_yes:
        for runner in market.get("runners") or []:
            runner_name = str(runner.get("runnerName") or "").strip()
            if not runner_name or runner_name.lower() in {"yes", "no", "over", "under", "neither", "draw"}:
                continue
            player = resolve_roster_player(runner_name, roster)
            add(build_yes_player_key(family_yes, player), family_yes, player, "Yes", runner_name)
        return results

    # --- Player shot tiers ---
    if "player to have" in low and "each half" not in low:
        if "shots on target" in low:
            family = "shots_on_target_player"
        elif "shot" in low:
            family = "shots_player"
        else:
            family = None
        if family:
            m = re.search(r"(\d+)\s+or more", low)
            tier = int(m.group(1)) if m else 1
            for runner in market.get("runners") or []:
                runner_name = str(runner.get("runnerName") or "").strip()
                if not runner_name:
                    continue
                player = resolve_roster_player(runner_name, roster)
                add(build_tier_player_key(family, player, tier), family, player, "Yes", runner_name)
            return results

    # --- Match shots (N+) ---
    if label == "Match Shots":
        for runner in market.get("runners") or []:
            runner_name = str(runner.get("runnerName") or "").strip()
            parsed = _parse_plus_runner(runner_name)
            if not parsed:
                continue
            _, tier = parsed
            add(build_tier_subject_key("shots_match", "match", tier), "shots_match", "match", "Yes", runner_name)
        return results

    # --- Team shots (N+) ---
    m = re.match(r"team to have (\d+) or more shots$", low)
    if m:
        tier = int(m.group(1))
        for runner in market.get("runners") or []:
            runner_name = str(runner.get("runnerName") or "").strip()
            if not runner_name:
                continue
            team = resolve_team_name(runner_name, home_team, away_team)
            add(build_tier_subject_key("shots_team", team, tier), "shots_team", team, "Yes", runner_name)
        return results

    # --- Corners O/U match ---
    m = re.match(r"total corners\s+([\d.]+)$", low)
    if m:
        line = float(m.group(1))
        key = build_ou_subject_key("corners_match", "match", line)
        for runner in market.get("runners") or []:
            runner_name = str(runner.get("runnerName") or "").strip()
            rlow = runner_name.lower()
            if rlow.startswith("over"):
                add(key, "corners_match", "match", "Over", runner_name)
            elif rlow.startswith("under"):
                add(key, "corners_match", "match", "Under", runner_name)
        return results

    # --- Corners O/U team ---
    m = re.match(r"(home|away)\s+total corners\s+([\d.]+)$", low)
    if m:
        side, line_s = m.group(1), m.group(2)
        line = float(line_s)
        team = home_team if side == "home" else away_team
        if not team:
            return results
        key = build_ou_subject_key("corners_team", team, line)
        for runner in market.get("runners") or []:
            runner_name = str(runner.get("runnerName") or "").strip()
            rlow = runner_name.lower()
            if rlow.startswith("over"):
                add(key, "corners_team", team, "Over", runner_name)
            elif rlow.startswith("under"):
                add(key, "corners_team", team, "Under", runner_name)
        return results

    return results


def format_soccer_ligne(*, family: str, player_name: str, outcome: str, compare_key: str) -> str:
    label = FAMILY_LABELS_FR.get(family, family)
    parts = compare_key.split("|")
    threshold = parts[2] if len(parts) >= 3 else ""
    if outcome in {"Yes", "Oui", "yes"}:
        issue = "Oui"
    elif outcome in {"Over", "Plus"}:
        issue = "Plus"
    elif outcome in {"Under", "Moins"}:
        issue = "Moins"
    else:
        issue = outcome
    subject = player_name or (parts[1] if len(parts) >= 2 else "")
    if threshold and threshold not in {"yes", "no"}:
        if subject and subject != "match":
            return f"{issue} {threshold} {label} — {subject}"
        return f"{issue} {threshold} {label}".strip()
    if subject and subject != "match":
        return f"{issue} {label} — {subject}"
    return f"{issue} {label}"
