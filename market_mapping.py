"""Correspondance marchés Coteur ↔ Pinnacle."""

from typing import Any

# Marchés Coteur exclus (handicaps, scores exacts)
COTEUR_EXCLUDED_TYPES = {"12", "12handi", "EXACT", "EXACTMT"}

COTEUR_TYPE_LABELS = {
    "1n2": "1X2",
    "OU": "Over/Under",
    "DC": "Double chance",
    "DNB": "Draw no bet",
    "HT": "Mi-temps 1X2",
    "HTDC": "Mi-temps double chance",
    "HTOU": "Mi-temps Over/Under",
    "BTTS": "Les 2 équipes marquent",
    "LTTS": "Une équipe ne marque pas",
    "HTFT": "Mi-temps / Fin de match",
    "BUTEUR": "Buteur",
    "FTTS": "Première équipe qui marque",
    "HT2": "Dernière équipe qui marque",
    "TOQ": "Qualification",
    "12": "Handicap 12",
    "EXACT": "Score exact",
    "EXACTMT": "Score exact mi-temps",
    "12handi": "Handicap 1X2",
}

# typename Coteur -> clé API Pinnacle (sans ligne)
COTEUR_TO_PINNACLE_BASE: dict[str, str | None] = {
    "1n2": "h2h",
    "OU": "totals",
    "DC": "double_chance",
    "DNB": "draw_no_bet",
    "HT": "h2h_h1",
    "HTDC": "double_chance_h1",
    "HTOU": "totals_h1",
    "BTTS": "btts",
    "LTTS": None,
    "HTFT": "halftime_fulltime",
    "BUTEUR": "player_goal_scorer_anytime",
    "FTTS": None,
    "TOQ": "to_qualify",
    "12": None,
    "12handi": None,
    "EXACT": None,
    "EXACTMT": None,
}


def coteur_market_key(typename: str, special: str) -> str:
    special = (special or "").strip()
    if special:
        return f"{typename}|{special}"
    return typename


def coteur_market_label(typename: str, special: str) -> str:
    base = COTEUR_TYPE_LABELS.get(typename, typename)
    special = (special or "").strip()
    if special and typename in ("OU", "HTOU"):
        line = special.replace("-", ".")
        return f"{base} {line}"
    if special and typename in ("12", "12handi"):
        return f"{base} {special.replace('-', '.')}"
    return base


def coteur_market_group_label(typename: str) -> str:
    return COTEUR_TYPE_LABELS.get(typename, typename)


def coteur_market_group_key(typename: str, special: str) -> str:
    special = (special or "").strip()
    if typename == "1n2" and special:
        return "1n2_handi"
    return typename


def coteur_market_group_display_label(typename: str, special: str) -> str:
    special = (special or "").strip()
    if typename == "1n2" and special:
        return "Handicap 1X2"
    return coteur_market_group_label(typename)


def coteur_market_variant_label(typename: str, special: str) -> str:
    special = (special or "").strip()
    if not special:
        return coteur_market_group_label(typename)
    if typename in ("OU", "HTOU"):
        return f"Ligne {special.replace('-', '.')}"
    if typename in ("12", "12handi", "1n2"):
        return f"Handicap {special.replace('-', '.')}"
    return special


def coteur_special_line(typename: str, special: str) -> float | str | None:
    special = (special or "").strip()
    if not special:
        return None
    if typename in ("OU", "HTOU"):
        try:
            return float(special.replace("-", "."))
        except ValueError:
            return special
    return special


def coteur_outcome_label(
    typename: str,
    outcome: str,
    home_team: str,
    away_team: str,
) -> str:
    mapping = {
        "1n2": {"0": "Nul", "1": home_team, "2": away_team},
        "DC": {"1": f"{home_team} ou Nul", "2": f"{away_team} ou Nul", "3": f"{home_team} ou {away_team}"},
        "DNB": {"1": home_team, "2": away_team},
        "HT": {"1": home_team, "2": "Nul", "3": away_team},
        "HTDC": {"1": f"{home_team} ou Nul", "2": f"{away_team} ou Nul", "3": f"{home_team} ou {away_team}"},
        "OU": {"2": "Under", "3": "Over"},
        "HTOU": {"2": "Under", "3": "Over"},
        "BTTS": {"1": "Oui", "2": "Non", "3": "Inconnu"},
        "LTTS": {"1": home_team, "2": away_team, "3": "aucune"},
        "FTTS": {"1": home_team, "2": away_team, "3": "aucune"},
        "HT2": {"1": home_team, "2": away_team, "3": "aucune"},
        "TOQ": {"1": home_team, "2": away_team, "3": "aucune"},
        "12": {"1": home_team, "2": away_team},
    }
    if typename == "HTFT":
        htft = {
            "1": f"{home_team}/{home_team}",
            "2": f"{home_team}/Nul",
            "3": f"{home_team}/{away_team}",
            "4": f"Nul/{home_team}",
            "5": "Nul/Nul",
            "6": f"Nul/{away_team}",
            "7": f"{away_team}/{home_team}",
            "8": f"{away_team}/Nul",
            "9": f"{away_team}/{away_team}",
        }
        return htft.get(outcome, outcome)
    if typename == "BUTEUR":
        return f"player:{outcome}"
    return mapping.get(typename, {}).get(outcome, outcome)


def pinnacle_market_key(market_key: str, point: str | float | None = None) -> str:
    if point not in (None, ""):
        return f"{market_key}|{point}"
    return market_key


def pinnacle_market_label(market_key: str, point: str | float | None = None) -> str:
    labels = {
        "h2h": "1X2",
        "totals": "Over/Under",
        "alternate_totals": "Over/Under (alt.)",
        "double_chance": "Double chance",
        "draw_no_bet": "Draw no bet",
        "h2h_h1": "Mi-temps 1X2",
        "h2h_3_way_h1": "Mi-temps 1X2",
        "double_chance_h1": "Mi-temps double chance",
        "totals_h1": "Mi-temps Over/Under",
        "alternate_totals_h1": "Mi-temps Over/Under (alt.)",
        "btts": "Les 2 équipes marquent",
        "btts_h1": "BTTS mi-temps",
        "halftime_fulltime": "Mi-temps / Fin de match",
        "player_goal_scorer_anytime": "Buteur",
        "player_first_goal_scorer": "Premier buteur",
        "to_qualify": "Qualification",
        "odd_even": "Pair/Impair",
        "odd_even_h1": "Pair/Impair mi-temps",
        "corners_1x2": "Corners 1X2",
        "alternate_totals_corners": "Corners Over/Under",
    }
    base = labels.get(market_key, market_key)
    if point not in (None, ""):
        return f"{base} {point}"
    return base


def map_coteur_to_pinnacle(typename: str, special: str) -> str | None:
    if typename in COTEUR_EXCLUDED_TYPES:
        return None
    base = COTEUR_TO_PINNACLE_BASE.get(typename)
    if base is None:
        return None
    special = (special or "").strip()
    if typename == "1n2" and special:
        return None
    if special and typename in ("OU", "HTOU"):
        line = special.replace("-", ".")
        return pinnacle_market_key(base, line)
    return base


def extract_coteur_markets(odds_payload: dict[str, Any]) -> list[dict[str, Any]]:
    markets = []
    for entry in odds_payload.get("odds", []):
        typename = entry.get("typename", "")
        special = entry.get("special", "") or ""
        if typename in COTEUR_EXCLUDED_TYPES:
            continue

        books_fr = set()
        for bucket in ("bestfr", "best"):
            for choice_data in (entry.get(bucket) or {}).values():
                if isinstance(choice_data, dict) and "bookId" in choice_data:
                    books_fr.add(choice_data["bookId"])

        markets.append({
            "key": coteur_market_key(typename, special),
            "typename": typename,
            "special": special,
            "label": coteur_market_label(typename, special),
            "pinnacle_key": map_coteur_to_pinnacle(typename, special),
            "outcomes": list((entry.get("bestfr") or entry.get("best") or {}).keys()),
            "book_ids": sorted(books_fr),
        })
    return markets


def extract_pinnacle_markets(event_odds: dict[str, Any]) -> list[dict[str, Any]]:
    pinnacle = next(
        (bm for bm in event_odds.get("bookmakers", []) if bm.get("key") == "pinnacle"),
        None,
    )
    if not pinnacle:
        return []

    markets = []
    for market in pinnacle.get("markets", []):
        market_key = market["key"]
        points = {
            str(o.get("point"))
            for o in market.get("outcomes", [])
            if o.get("point") is not None
        }
        if points:
            for point in sorted(points, key=lambda x: float(x) if x else 0):
                markets.append({
                    "key": pinnacle_market_key(market_key, point),
                    "market_key": market_key,
                    "point": point,
                    "label": pinnacle_market_label(market_key, point),
                    "outcomes": [
                        o.get("name", "")
                        for o in market.get("outcomes", [])
                        if str(o.get("point", "")) == point or o.get("point") == float(point)
                    ],
                })
        else:
            markets.append({
                "key": market_key,
                "market_key": market_key,
                "point": "",
                "label": pinnacle_market_label(market_key),
                "outcomes": [o.get("name", "") for o in market.get("outcomes", [])],
            })
    return markets
