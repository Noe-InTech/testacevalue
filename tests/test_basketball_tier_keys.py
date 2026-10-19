"""Clés +N pour paliers Unibet / FanDuel."""

from __future__ import annotations

import unittest

from basketball_books_mapping import normalize_unibet_market
from basketball_market_mapping import build_player_tier_prop_key


class BasketballTierKeyTests(unittest.TestCase):
    def test_unibet_rebound_tier_uses_plus_key(self) -> None:
        markets = normalize_unibet_market(
            "Nbre de rebonds - Joueur - Match",
            [("Duncan Robinson 4+", 2.2)],
            ["Duncan Robinson"],
        )
        self.assertEqual(len(markets), 1)
        self.assertEqual(
            markets[0].compare_key,
            build_player_tier_prop_key("rebounds_player", "Duncan Robinson", 4),
        )
        self.assertEqual(markets[0].line, "+4")


if __name__ == "__main__":
    unittest.main()
