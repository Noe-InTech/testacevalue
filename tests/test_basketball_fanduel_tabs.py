"""Onglets FanDuel basketball — couverture Alt Rebounds / props par stat."""

from __future__ import annotations

import unittest

from basketball_constants import FANDUEL_NBA_EVENT_TABS


class FanDuelBasketballTabsTests(unittest.TestCase):
    def test_includes_player_rebounds_tab(self) -> None:
        self.assertIn("player-rebounds", FANDUEL_NBA_EVENT_TABS)

    def test_includes_core_player_stat_tabs(self) -> None:
        for tab in (
            "player-points",
            "player-rebounds",
            "player-assists",
            "player-threes",
            "player-combos",
        ):
            self.assertIn(tab, FANDUEL_NBA_EVENT_TABS)


if __name__ == "__main__":
    unittest.main()
