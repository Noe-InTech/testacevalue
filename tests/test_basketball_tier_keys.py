"""Clés +N pour paliers Unibet / FanDuel."""

from __future__ import annotations

import unittest

from basketball_books_mapping import normalize_unibet_market
from basketball_market_mapping import (
    build_player_prop_key,
    build_player_tier_prop_key,
    resolve_fanduel_match_for_fr_prop,
)


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

    def test_unibet_tier_prefers_fanduel_alt_ou_over_tier_market(self) -> None:
        tier_key = build_player_tier_prop_key("rebounds_player", "Duncan Robinson", 4)
        ou_key = build_player_prop_key("rebounds_player", "Duncan Robinson", "3.5")
        fd_map = {
            ou_key: {
                "market_label": "Duncan Robinson - Alt Rebounds",
                "outcomes": {
                    "Over": {"decimal_fr": 3.2, "american": 220},
                    "Under": {"decimal_fr": 1.32, "american": -310},
                },
            },
            tier_key: {
                "market_label": "To Record 4+ Rebounds",
                "outcomes": {"Over": {"decimal_fr": 3.2, "american": 220}},
            },
        }
        match = resolve_fanduel_match_for_fr_prop(tier_key, "Over", fd_map)
        self.assertIsNotNone(match)
        fd_market, fd_outcome, fd_key = match
        self.assertEqual(fd_key, ou_key)
        self.assertEqual(fd_outcome, "Over")
        self.assertIn("Alt Rebounds", fd_market["market_label"])

    def test_unibet_tier_three_plus_maps_to_fd_two_point_five(self) -> None:
        tier_key = build_player_tier_prop_key("rebounds_player", "Duncan Robinson", 3)
        ou_key = build_player_prop_key("rebounds_player", "Duncan Robinson", "2.5")
        fd_map = {
            ou_key: {
                "market_label": "Duncan Robinson - Alt Rebounds",
                "outcomes": {"Over": {"decimal_fr": 1.85, "american": -118}},
            },
        }
        match = resolve_fanduel_match_for_fr_prop(tier_key, "Over", fd_map)
        self.assertIsNotNone(match)
        self.assertEqual(match[2], ou_key)


if __name__ == "__main__":
    unittest.main()
