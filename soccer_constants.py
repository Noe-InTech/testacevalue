"""Constantes foot — familles comparables FR ↔ US."""

from __future__ import annotations

BOOK_LABELS = {
    "winamax": "Winamax",
    "unibet": "Unibet",
    "betclic": "Betclic",
}

FANDUEL_SOCCER_EVENT_TYPE_ID = "1"
FANDUEL_SOCCER_EVENT_TABS = ("popular", "shots", "goalscorer", "player-props", "corners")

# Fallback si la découverte auto échoue
FANDUEL_SOCCER_COMPETITION_IDS: tuple[str, ...] = (
    "55",
    "10932509",
    "117",
    "81",
    "59",
    "141",
    "228",
    "12242357",
    "12243231",
    "12351533",
    "11201",
    "11984200",
    "11068551",
    "9404054",
    "105",
    "89979",
    "7129730",
    "61",
    "10479956",
    "13",
    "139",
)

WINAMAX_FOOTBALL_SPORT_ID = 1

BETCLIC_SOCCER_HUB_PATH = "/football-sfootball"
BETCLIC_SOCCER_LISTING_PATHS: tuple[str, ...] = (
    "/football-sfootball",
    "/football-sfootball/ligue-1-mcdonald-s-c4",
    "/football-sfootball/angl-premier-league-c3",
    "/football-sfootball/espagne-laliga-c7",
    "/football-sfootball/italie-serie-a-c6",
    "/football-sfootball/allemagne-bundesliga-c5",
    "/football-sfootball/mls-c19",
    "/football-sfootball/ligue-des-champions-c8",
    "/football-sfootball/europa-league-c9",
    "/football-sfootball/europa-conference-league-c13347",
    "/football-sfootball/norvege-eliteserien-c156",
    "/football-sfootball/ecosse-premiership-c33",
    "/football-sfootball/autriche-bundesliga-c35",
    "/football-sfootball/belgique-jupiler-pro-league-c16",
    "/football-sfootball/bundesliga-2-c44",
    "/football-sfootball/ukraine-premier-league-c530",
)

COMPARABLE_FAMILIES: tuple[str, ...] = (
    "anytime_goalscorer",
    "first_goalscorer",
    "score_or_assist",
    "anytime_assist",
    "shots_player",
    "shots_on_target_player",
    "shots_match",
    "shots_team",
    "shots_on_target_match",
    "shots_on_target_team",
    "player_card",
    "corners_match",
    "corners_team",
)

FAMILY_LABELS_FR: dict[str, str] = {
    "anytime_goalscorer": "Buteur",
    "first_goalscorer": "1er buteur",
    "score_or_assist": "Décisif",
    "anytime_assist": "Passeur",
    "shots_player": "Tirs joueur",
    "shots_on_target_player": "Tirs cadrés joueur",
    "shots_match": "Tirs match",
    "shots_team": "Tirs équipe",
    "shots_on_target_match": "Tirs cadrés match",
    "shots_on_target_team": "Tirs cadrés équipe",
    "player_card": "Carton",
    "corners_match": "Corners match",
    "corners_team": "Corners équipe",
}
