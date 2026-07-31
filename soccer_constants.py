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
    # Big 5 + MLS
    "55",  # French Ligue 1
    "10932509",  # English Premier League
    "117",  # Spanish La Liga
    "81",  # Italian Serie A
    "59",  # German Bundesliga
    "141",  # MLS
    # UEFA
    "228",  # UEFA Champions League
    "12242357",  # UEFA Champions League Qualifiers
    "12243231",  # UEFA Europa League Qualifiers
    "12351533",  # UEFA Europa Conference League Qualifiers
    "11201",  # UEFA Super Cup
    "11984200",  # UEFA Nations League
    # Autres ligues fortes / actives
    "11068551",  # Norwegian Eliteserien
    "9404054",  # Dutch Eredivisie
    "105",  # Scottish Premiership
    "89979",  # Belgian Pro League
    "7129730",  # English Championship
    "61",  # German Bundesliga 2
    "10479956",  # Austrian Bundesliga
    "13",  # Brazilian Serie A
    "139",  # Ukrainian Premier League
)

BETCLIC_SOCCER_HUB_PATH = "/football-sfootball"
BETCLIC_SOCCER_LISTING_PATHS: tuple[str, ...] = (
    "/football-sfootball",
    # Big 5 + MLS
    "/football-sfootball/ligue-1-mcdonald-s-c4",
    "/football-sfootball/angl-premier-league-c3",
    "/football-sfootball/espagne-laliga-c7",
    "/football-sfootball/italie-serie-a-c6",
    "/football-sfootball/allemagne-bundesliga-c5",
    "/football-sfootball/mls-c19",
    # UEFA
    "/football-sfootball/ligue-des-champions-c8",
    "/football-sfootball/europa-league-c9",
    "/football-sfootball/europa-conference-league-c13347",
    # Autres
    "/football-sfootball/norvege-eliteserien-c156",
    "/football-sfootball/ecosse-premiership-c33",
    "/football-sfootball/autriche-bundesliga-c35",
    "/football-sfootball/belgique-jupiler-pro-league-c16",
    "/football-sfootball/bundesliga-2-c44",
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
