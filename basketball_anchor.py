"""Fusion d'ancres basketball (NBA/WNBA) — un match = une fiche, tous books."""

from __future__ import annotations

from typing import Any, Callable

TeamsMatch = Callable[[str, str, str, str], bool]


def _prefer_team_label(current: str, incoming: str, *, teams_match: TeamsMatch) -> str:
    a = str(current or "").strip()
    b = str(incoming or "").strip()
    if not a:
        return b
    if not b:
        return a
    if teams_match(a, b, b, a):
        return a if len(a) >= len(b) else b
    return a


def anchor_storage_key(home: str, away: str) -> str:
    return f"{home.lower()}|{away.lower()}"


def resolve_merged_anchor_key(
    anchors: dict[str, dict[str, Any]],
    home: str,
    away: str,
    *,
    teams_match: TeamsMatch,
) -> str:
    """Retrouve l'ancre existante (noms d'equipes abbrevies ou complets, home/away inverses)."""
    for key, anchor in anchors.items():
        if teams_match(anchor["home_team"], anchor["away_team"], home, away):
            return key
    return anchor_storage_key(home, away)


def new_basketball_anchor(home: str, away: str) -> dict[str, Any]:
    return {
        "home_team": home,
        "away_team": away,
        "match": f"{home} vs {away}",
        "sources": set(),
        "urls": {},
        "unibet_event_id": None,
        "betclic_match_id": None,
        "winamax_match_id": None,
        "fanduel_event_id": None,
        "is_live": False,
    }


def attach_basketball_anchor(
    anchors: dict[str, dict[str, Any]],
    home: str,
    away: str,
    *,
    teams_match: TeamsMatch,
) -> dict[str, Any]:
    """Cree ou reutilise l'ancre canonique pour cette paire d'equipes."""
    key = resolve_merged_anchor_key(anchors, home, away, teams_match=teams_match)
    if key not in anchors:
        anchors[key] = new_basketball_anchor(home, away)
    anchor = anchors[key]
    if teams_match(anchor["home_team"], anchor["away_team"], home, away):
        anchor["home_team"] = _prefer_team_label(anchor["home_team"], home, teams_match=teams_match)
        anchor["away_team"] = _prefer_team_label(anchor["away_team"], away, teams_match=teams_match)
    elif teams_match(anchor["home_team"], anchor["away_team"], away, home):
        anchor["home_team"] = _prefer_team_label(anchor["home_team"], away, teams_match=teams_match)
        anchor["away_team"] = _prefer_team_label(anchor["away_team"], home, teams_match=teams_match)
    anchor["match"] = f"{anchor['home_team']} vs {anchor['away_team']}"
    return anchor
