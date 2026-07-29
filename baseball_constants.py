"""Constantes baseball MLB / KBO (pipeline séparé tennis / basket)."""

from __future__ import annotations

# FanDuel sbapi
FANDUEL_BASEBALL_EVENT_TYPE_ID = "7511"
FANDUEL_MLB_COMPETITION_ID = "11196870"
FANDUEL_KBO_COMPETITION_ID = "11085810"
FANDUEL_CPBL_COMPETITION_ID = "12290183"
FANDUEL_MLB_CONTENT_PAGE = "mlb"

FANDUEL_BASEBALL_COMPETITION_IDS = (
    FANDUEL_MLB_COMPETITION_ID,
    FANDUEL_KBO_COMPETITION_ID,
    FANDUEL_CPBL_COMPETITION_ID,
)

FANDUEL_BASEBALL_EVENT_TABS = (
    "popular",
    "all-markets",
    "player-props",
    "game-lines",
    "pitcher-props",
    "batter-props",
    "same-game-parlay-",
)

# Winamax Socket.IO
WINAMAX_BASEBALL_SPORT_ID = 3
WINAMAX_MLB_TOURNAMENT_ID = 25
WINAMAX_KBO_TOURNAMENT_ID = 4395

# Unibet listing
UNIBET_BASEBALL_LISTING_PATH = "/paris-baseball"
UNIBET_MLB_LISTING_PATH = "/paris-baseball/mlb/mlb"
UNIBET_KBO_LISTING_PATH = "/paris-baseball/coree-du-sud/kbo"

BOOK_LABELS = {
    "unibet": "Unibet",
    "winamax": "Winamax",
}

COMPARABLE_FAMILIES = frozenset(
    {
        "h2h",
        "run_line",
        "runs_total",
        "runs_team",
        "f5_h2h",
        "f5_run_line",
        "f5_runs_total",
        "inning1_result",
        "inning1_runs_total",
        "hr_player",
        "runs_player",
        "strikeouts_pitcher",
    }
)

TEAM_SIDE_OUTCOMES = frozenset({"home", "away", "draw"})
OU_OUTCOMES = frozenset({"Over", "Under"})
YES_OUTCOMES = frozenset({"Yes"})
