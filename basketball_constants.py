"""Constantes WNBA / basketball (séparé du pipeline tennis)."""

from __future__ import annotations

# FanDuel sbapi
FANDUEL_BASKETBALL_EVENT_TYPE_ID = "7522"
FANDUEL_WNBA_COMPETITION_ID = "11295025"
FANDUEL_WNBA_EVENT_TABS = (
    "popular",
    "all-markets",
    "player-props",
    "same-game-parlay-",
)

# Winamax Socket.IO
WINAMAX_BASKETBALL_SPORT_ID = 2

# Unibet listing
UNIBET_BASKETBALL_LISTING_PATH = "/paris-basketball"

# Betclic listing + catégories gRPC stats joueuses
BETCLIC_WNBA_LISTING_PATH = "/basketball-sbasketball"
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
