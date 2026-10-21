"""Noms d'équipes Euroleague — appariement strict entre books.

Hapoel Tel-Aviv et Maccabi Tel-Aviv partagent la ville. Un recouvrement de
tokens les collerait sur le même match. On ne retient qu'un club canonique.
"""

from __future__ import annotations

import re
import unicodedata

# Phrases les plus longues d'abord (fenerbahce avant fener, milano avant milan).
_CLUB_PHRASES: tuple[tuple[str, str], ...] = (
    ("etoile rouge", "Crvena Zvezda"),
    ("crvena zvezda", "Crvena Zvezda"),
    ("red star", "Crvena Zvezda"),
    ("er belgrade", "Crvena Zvezda"),
    ("mac tel aviv", "Maccabi Tel Aviv"),
    ("emporio milano", "Olimpia Milano"),
    ("hapoel", "Hapoel Tel Aviv"),
    ("maccabi", "Maccabi Tel Aviv"),
    ("virtus", "Virtus Bologna"),
    ("bologne", "Virtus Bologna"),
    ("bologna", "Virtus Bologna"),
    ("anadolu", "Anadolu Efes"),
    ("efes", "Anadolu Efes"),
    ("besiktas", "Besiktas"),
    ("bayern", "Bayern Munich"),
    ("dubai", "Dubai Basketball"),
    ("real madrid", "Real Madrid"),
    ("madrid", "Real Madrid"),
    ("panathinaikos", "Panathinaikos"),
    ("baskonia", "Baskonia"),
    ("vitoria", "Baskonia"),
    ("olimpia", "Olimpia Milano"),
    ("armani", "Olimpia Milano"),
    ("milano", "Olimpia Milano"),
    ("milan", "Olimpia Milano"),
    ("barcelone", "FC Barcelona"),
    ("barcelona", "FC Barcelona"),
    ("partizan", "Partizan Belgrade"),
    ("zalgiris", "Zalgiris Kaunas"),
    ("villeurbanne", "ASVEL"),
    ("asvel", "ASVEL"),
    ("olympiacos", "Olympiacos"),
    ("olympiakos", "Olympiacos"),
    ("fenerbahce", "Fenerbahce"),
    ("fener", "Fenerbahce"),
    ("paris", "Paris Basketball"),
    ("valence", "Valencia Basket"),
    ("valencia", "Valencia Basket"),
)


def _normalize_club_text(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower().replace("-", " ").replace("_", " ")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def canonical_euroleague_club(name: str) -> str | None:
    """Nom d'affichage stable, ou None si ce n'est pas un club Euroleague connu."""
    text = _normalize_club_text(name)
    if not text:
        return None
    padded = f" {text} "
    for phrase, club in _CLUB_PHRASES:
        if f" {phrase} " in padded:
            return club
    return None


def euroleague_display_name(name: str) -> str:
    return canonical_euroleague_club(name) or str(name or "").strip()


def split_euroleague_clubs(name: str) -> tuple[str, str]:
    """Deux clubs distincts dans un libellé ou un slug, dans l'ordre d'apparition."""
    text = _normalize_club_text(name)
    if not text:
        return "", ""
    found: list[tuple[int, str]] = []
    occupied: set[int] = set()
    for phrase, club in _CLUB_PHRASES:
        for match in re.finditer(rf"(?:^| ){re.escape(phrase)}(?: |$)", text):
            span = set(range(match.start(), match.end()))
            if span & occupied:
                continue
            if any(existing == club for _, existing in found):
                occupied.update(span)
                continue
            found.append((match.start(), club))
            occupied.update(span)
            break
    found.sort(key=lambda item: item[0])
    if len(found) < 2:
        return "", ""
    return found[0][1], found[1][1]


def euroleague_teams_match(home_a: str, away_a: str, home_b: str, away_b: str) -> bool:
    """Même paire de clubs, dans n'importe quel ordre. Pas de repli flou."""
    left = {canonical_euroleague_club(home_a), canonical_euroleague_club(away_a)}
    right = {canonical_euroleague_club(home_b), canonical_euroleague_club(away_b)}
    if None in left or None in right:
        return False
    return left == right
