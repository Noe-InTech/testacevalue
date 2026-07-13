"""Constantes WNBA / basketball (séparé du pipeline tennis)."""

from __future__ import annotations

# FanDuel sbapi
FANDUEL_BASKETBALL_EVENT_TYPE_ID = "7522"
FANDUEL_WNBA_COMPETITION_ID = "11295025"
# Summer League + page NBA (content-managed-page); awards/futures exclus au filtre.
FANDUEL_NBA_SUMMER_LEAGUE_COMPETITION_ID = "12669662"
FANDUEL_NBA_COMPETITION_IDS = (
    FANDUEL_NBA_SUMMER_LEAGUE_COMPETITION_ID,
)
FANDUEL_NBA_COMPETITION_ID = FANDUEL_NBA_SUMMER_LEAGUE_COMPETITION_ID
FANDUEL_NBA_CONTENT_PAGE = "nba"
FANDUEL_WNBA_EVENT_TABS = (
    "popular",
    "all-markets",
    "player-props",
    "same-game-parlay-",
)

FANDUEL_NBA_EVENT_TABS = FANDUEL_WNBA_EVENT_TABS

# Winamax Socket.IO
WINAMAX_BASKETBALL_SPORT_ID = 2

# Unibet listing
UNIBET_BASKETBALL_LISTING_PATH = "/paris-basketball"

# Betclic listing + catégories gRPC stats joueurs (WNBA + NBA)
BETCLIC_WNBA_LISTING_PATH = "/basketball-sbasketball"
BETCLIC_NBA_LISTING_PATH = BETCLIC_WNBA_LISTING_PATH
BETCLIC_NBA_COMPETITION_PREFIX = "nba-c13"
UNIBET_NBA_PATH_FRAGMENT = "/paris-basketball/usa/nba/"
UNIBET_NBA_HUB_PATHS = (
    "/paris-basketball/usa/nba/3351280/nba-26-27",
)
BASKETBALL_OUTRIGHT_SLUG_MARKERS = (
    "nba-20",
    "nba-26",
    "nba-cup",
    "wnba-20",
    "futures",
    "saison",
    "vainqueur",
    "champion",
)
BETCLIC_BASKETBALL_GRPC_CATEGORIES = (
    "ca_bkb_pts",
    "ca_bkb_pprp",
    "ca_bkb_scrs",
    "ca_bkb_rsl",
)

PLAYER_PROP_FAMILIES = frozenset(
    {
        "points_player",
        "rebounds_player",
        "assists_player",
        "threes_made_player",
        "blocks_player",
        "steals_player",
        "turnovers_player",
        "points_rebounds_player",
        "points_assists_player",
        "rebounds_assists_player",
        "pra_player",
        "double_double_player",
    }
)

BOOK_LABELS = {
    "unibet": "Unibet",
    "betclic": "Betclic",
    "winamax": "Winamax",
}
