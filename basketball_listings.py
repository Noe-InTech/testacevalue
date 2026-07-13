"""Helpers partagés — découverte matchs WNBA / NBA."""

from __future__ import annotations

import re

from basketball_constants import BASKETBALL_OUTRIGHT_SLUG_MARKERS


def is_basketball_outright_slug(slug: str) -> bool:
    lower = slug.lower()
    if any(marker in lower for marker in BASKETBALL_OUTRIGHT_SLUG_MARKERS):
        return True
    if re.search(r"nba-\d{4}-\d{4}$", lower):
        return True
    return "-vs-" not in lower and "-at-" not in lower and "-v-" not in lower


def is_fanduel_nba_game_event(name: str) -> bool:
    text = str(name or "").strip()
    if not text:
        return False
    lower = text.lower()
    if any(token in lower for token in ("futures", "awards", "draft", "championship odds")):
        return False
    if "(" in text or ")" in text:
        return False
    if " @ " not in text and " at " not in lower:
        return False
    home, away = split_match_teams_from_name(text)
    return bool(home and away)


def split_match_teams_from_name(name: str) -> tuple[str, str]:
    text = str(name or "").strip()
    if " @ " in text:
        away, home = text.split(" @ ", 1)
        return home.strip(), away.strip()
    if " at " in text.lower():
        parts = re.split(r"\s+at\s+", text, maxsplit=1, flags=re.I)
        if len(parts) == 2:
            return parts[1].strip(), parts[0].strip()
    return "", ""
