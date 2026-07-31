"""Constantes foot — familles comparables FR ↔ US."""

from __future__ import annotations

BOOK_LABELS = {
    "winamax": "Winamax",
    "unibet": "Unibet",
    "betclic": "Betclic",
}

# FanDuel soccer = eventTypeId 1
FANDUEL_SOCCER_EVENT_TYPE_ID = "1"
FANDUEL_SOCCER_EVENT_TABS = ("popular", "shots", "goalscorer", "player-props")

# Competitions à scanner (props joueur souvent près du KO)
FANDUEL_SOCCER_COMPETITION_IDS: tuple[str, ...] = (
    "11068551",  # Norwegian Eliteserien
    "141",  # MLS
    "55",  # French Ligue 1
    "10932509",  # English Premier League
    "117",  # Spanish La Liga
    "81",  # Italian Serie A
    "59",  # German Bundesliga
    "13",  # Brazilian Serie A
    "139",  # Ukrainian Premier League
)

BETCLIC_SOCCER_HUB_PATH = "/football-sfootball"
BETCLIC_SOCCER_LISTING_PATHS: tuple[str, ...] = (
    "/football-sfootball",
    "/football-sfootball/ligue-1-mcdonald-s-c4",
    "/football-sfootball/mls-c19",
    "/football-sfootball/norvege-eliteserien-c156",
    "/football-sfootball/premier-league-c3",
    "/football-sfootball/liga-c7",
    "/football-sfootball/serie-a-c6",
    "/football-sfootball/bundesliga-c5",
    "/football-sfootball/ukraine-premier-league-c530",
)

# Familles canoniques (pills UI)
COMPARABLE_FAMILIES: tuple[str, ...] = (
    "anytime_goalscorer",
    "first_goalscorer",
    "score_or_assist",
    "anytime_assist",
    "shots_player",
    "shots_on_target_player",
    "player_card",
    "corners_match",
)

FAMILY_LABELS_FR: dict[str, str] = {
    "anytime_goalscorer": "Buteur",
    "first_goalscorer": "1er buteur",
    "score_or_assist": "Décisif",
    "anytime_assist": "Passeur",
    "shots_player": "Tirs",
    "shots_on_target_player": "Tirs cadrés",
    "player_card": "Carton",
    "corners_match": "Corners",
}
