"""Helpers listing / filtres baseball."""

from __future__ import annotations

import re

from baseball_market_mapping import strip_accents


OUTRIGHT_MARKERS = (
    "futures",
    "awards",
    "saison",
    "vainqueur",
    "champion",
    "outright",
    "mlb-20",
    "kbo-20",
    "player markets",
    "player awards",
)


def is_baseball_outright_name(name: str) -> bool:
    lower = strip_accents(name)
    return any(marker in lower for marker in OUTRIGHT_MARKERS)


def looks_like_game_name(name: str) -> bool:
    text = str(name or "").strip()
    if not text or is_baseball_outright_name(text):
        return False
    return bool(
        re.search(r"\s[@v]\s|\svs\.?\s|\s-\s", text, flags=re.I)
        or " @ " in text
        or " vs " in text.lower()
    )


def competition_from_blob(*parts: str) -> str:
    blob = strip_accents(" ".join(parts))
    if "kbo" in blob or "coree" in blob or "korea" in blob:
        return "KBO"
    if "cpbl" in blob or "taipei" in blob or "taiwan" in blob:
        return "CPBL"
    if "npb" in blob or "japon" in blob or "japan" in blob:
        return "NPB"
    if "mlb" in blob or "major league" in blob:
        return "MLB"
    # Heuristic on known KBO nicknames without MLB collision
    kbo_markers = (
        "hanwha",
        "kiwoom",
        "doosan",
        "ssg landers",
        "kt wiz",
        "nc dinos",
        "lg twins",
        "lotte giants",
        "kia tigers",
        "samsung lions",
    )
    if any(marker in blob for marker in kbo_markers):
        # Avoid SF Giants / Detroit Tigers false positives — those include city names.
        if not any(
            city in blob
            for city in (
                "san francisco",
                "detroit",
                "new york",
                "los angeles",
                "boston",
                "chicago",
            )
        ):
            return "KBO"
    return "MLB"
