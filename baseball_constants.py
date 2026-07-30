"""Constantes baseball MLB / KBO / NPB (pipeline séparé tennis / basket)."""

from __future__ import annotations

import re

# FanDuel sbapi
FANDUEL_BASEBALL_EVENT_TYPE_ID = "7511"
FANDUEL_MLB_COMPETITION_ID = "11196870"
FANDUEL_KBO_COMPETITION_ID = "11085810"
FANDUEL_CPBL_COMPETITION_ID = "12290183"
# FanDuel NPB not listed yet (probe /api/content-managed-page eventTypeId=7511).
FANDUEL_NPB_COMPETITION_ID = ""
FANDUEL_MLB_CONTENT_PAGE = "mlb"

FANDUEL_BASEBALL_COMPETITION_IDS = tuple(
    cid
    for cid in (
        FANDUEL_MLB_COMPETITION_ID,
        FANDUEL_KBO_COMPETITION_ID,
        FANDUEL_CPBL_COMPETITION_ID,
        FANDUEL_NPB_COMPETITION_ID,
    )
    if cid
)

FANDUEL_BASEBALL_EVENT_TABS = (
    "popular",
    "player-props",
    "batter-props",
    "pitcher-props",
    "game-lines",
    "all-markets",
    # same-game-parlay intentionally omitted: not comparable + slows scrape
)

# Winamax Socket.IO
WINAMAX_BASEBALL_SPORT_ID = 3
WINAMAX_MLB_TOURNAMENT_ID = 25
WINAMAX_KBO_TOURNAMENT_ID = 4395
WINAMAX_NPB_TOURNAMENT_ID = 20546

# Unibet listing
UNIBET_BASEBALL_LISTING_PATH = "/paris-baseball"
UNIBET_MLB_LISTING_PATH = "/paris-baseball/mlb/mlb"
UNIBET_KBO_LISTING_PATH = "/paris-baseball/coree-du-sud/kbo"
UNIBET_NPB_LISTING_PATH = "/paris-baseball/japon/npb"

# Betclic listing (hub + MLB ; KBO ressort du hub si dispo)
BETCLIC_BASEBALL_LISTING_PATH = "/baseball-sbaseball"
BETCLIC_MLB_LISTING_PATH = "/baseball-sbaseball/major-league-c473"
BETCLIC_BASEBALL_LISTING_PATHS = (
    BETCLIC_BASEBALL_LISTING_PATH,
    BETCLIC_MLB_LISTING_PATH,
)
BETCLIC_BASEBALL_MATCH_HREF_RE = re.compile(
    r'href="(/baseball-sbaseball/[^"]+-m\d+)"',
    flags=re.I,
)

BOOK_LABELS = {
    "unibet": "Unibet",
    "betclic": "Betclic",
    "winamax": "Winamax",
}

COMPARABLE_FAMILIES = frozenset(
    {
        "h2h",
        "runs_total",
        "runs_team",
        "f5_h2h",
        "f5_runs_total",
        "inning1_result",
        "inning1_runs_total",
        "hr_player",
        "runs_player",
        "hits_player",
        "rbi_player",
        "total_bases_player",
        "sb_player",
        "strikeouts_pitcher",
    }
)

TEAM_SIDE_OUTCOMES = frozenset({"home", "away", "draw"})
OU_OUTCOMES = frozenset({"Over", "Under"})
YES_OUTCOMES = frozenset({"Yes"})
