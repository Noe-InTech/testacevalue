"""Clés +N pour paliers Unibet / FanDuel."""

from __future__ import annotations

import unittest

from basketball_books_mapping import normalize_unibet_market
from basketball_market_mapping import (
    build_player_prop_key,
    build_player_tier_prop_key,
    ou_line_to_tier_threshold,
    player_prop_keys_same_bet,
    resolve_fanduel_match_for_fr_prop,
)
from compare_wnba_props_vs_fanduel import compare_normalized_props


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

    def test_half_point_over_maps_to_next_tier_on_every_stat(self) -> None:
        cases = (
            ("points_player", "19.5", 20),
            ("rebounds_player", "4.5", 5),
            ("assists_player", "9.5", 10),
            ("threes_made_player", "2.5", 3),
            ("blocks_player", "0.5", 1),
            ("pra_player", "26.5", 27),
            ("points_rebounds_player", "14.5", 15),
            ("points_assists_player", "22.5", 23),
            ("rebounds_assists_player", "9.5", 10),
            ("steals_player", "1.5", 2),
        )
        for family, line, threshold in cases:
            self.assertEqual(ou_line_to_tier_threshold(line), threshold)
            ou_key = build_player_prop_key(family, "Anthony Davis", line)
            tier_key = build_player_tier_prop_key(family, "Anthony Davis", threshold)
            fd_map = {
                tier_key: {
                    "market_label": f"To Score {threshold}+",
                    "outcomes": {"Over": {"decimal_fr": 2.1, "american": 110}},
                }
            }
            match = resolve_fanduel_match_for_fr_prop(ou_key, "Over", fd_map)
            self.assertIsNotNone(match, family)
            self.assertEqual(match[2], tier_key)
            self.assertEqual(match[1], "Over")
            self.assertTrue(player_prop_keys_same_bet(ou_key, tier_key))

    def test_conversions_that_must_not_match(self) -> None:
        self.assertIsNone(ou_line_to_tier_threshold("19"))
        self.assertIsNone(ou_line_to_tier_threshold("20"))
        self.assertIsNone(ou_line_to_tier_threshold("19.25"))
        self.assertIsNone(ou_line_to_tier_threshold("+20"))
        self.assertIsNone(ou_line_to_tier_threshold("0"))
        ou_key = build_player_prop_key("points_player", "Anthony Davis", "19.5")
        tier_20 = build_player_tier_prop_key("points_player", "Anthony Davis", 20)
        tier_19 = build_player_tier_prop_key("points_player", "Anthony Davis", 19)
        tier_21 = build_player_tier_prop_key("points_player", "Anthony Davis", 21)
        other = build_player_tier_prop_key("points_player", "Trae Young", 20)
        fd_map = {
            tier_20: {"outcomes": {"Over": {"decimal_fr": 2.1, "american": 110}}},
            tier_19: {"outcomes": {"Over": {"decimal_fr": 1.4, "american": -250}}},
            tier_21: {"outcomes": {"Over": {"decimal_fr": 3.2, "american": 220}}},
            other: {"outcomes": {"Over": {"decimal_fr": 2.1, "american": 110}}},
        }
        self.assertEqual(resolve_fanduel_match_for_fr_prop(ou_key, "Over", fd_map)[2], tier_20)
        self.assertIsNone(resolve_fanduel_match_for_fr_prop(ou_key, "Under", fd_map))
        over_20_5 = build_player_prop_key("points_player", "Anthony Davis", "20.5")
        self.assertEqual(
            resolve_fanduel_match_for_fr_prop(over_20_5, "Over", fd_map)[2],
            tier_21,
        )
        integer_20 = build_player_prop_key("points_player", "Anthony Davis", "20")
        self.assertIsNone(resolve_fanduel_match_for_fr_prop(integer_20, "Over", fd_map))
        self.assertFalse(player_prop_keys_same_bet(ou_key, tier_21))
        self.assertFalse(player_prop_keys_same_bet(ou_key, other))
        self.assertFalse(
            player_prop_keys_same_bet(
                build_player_tier_prop_key("points_player", "Anthony Davis", 20),
                build_player_prop_key("points_player", "Anthony Davis", "20.5"),
            )
        )

    def test_exact_ou_wins_over_milestone(self) -> None:
        ou_key = build_player_prop_key("points_player", "Anthony Davis", "19.5")
        tier_key = build_player_tier_prop_key("points_player", "Anthony Davis", 20)
        fd_map = {
            ou_key: {
                "market_label": "Anthony Davis - Points",
                "outcomes": {
                    "Over": {"decimal_fr": 1.91, "american": -110},
                    "Under": {"decimal_fr": 1.91, "american": -110},
                },
            },
            tier_key: {
                "market_label": "To Score 20+ Points",
                "outcomes": {"Over": {"decimal_fr": 1.91, "american": -110}},
            },
        }
        self.assertEqual(resolve_fanduel_match_for_fr_prop(ou_key, "Over", fd_map)[2], ou_key)
        self.assertEqual(resolve_fanduel_match_for_fr_prop(ou_key, "Under", fd_map)[2], ou_key)
        self.assertEqual(resolve_fanduel_match_for_fr_prop(tier_key, "Over", fd_map)[2], ou_key)

    def test_display_names_both_writings_and_skips_value_without_under(self) -> None:
        ou_key = build_player_prop_key("points_player", "Anthony Davis", "19.5")
        tier_key = build_player_tier_prop_key("points_player", "Anthony Davis", 20)
        fr_map = {
            ou_key: {
                "market_family": "points_player",
                "player_name": "Anthony Davis",
                "market_label_raw": "Points",
                "outcomes": {
                    "Over": {
                        "odds": 1.85,
                        "bookmaker_label": "Betclic",
                        "by_book": {},
                    }
                },
            },
            tier_key: {
                "market_family": "points_player",
                "player_name": "Anthony Davis",
                "market_label_raw": "20+ points",
                "outcomes": {
                    "Over": {
                        "odds": 1.9,
                        "bookmaker_label": "Unibet",
                        "by_book": {},
                    }
                },
            },
        }
        fd_only_tier = {
            tier_key: {
                "market_label": "To Score 20+ Points",
                "outcomes": {"Over": {"decimal_fr": 2.05, "american": 105}},
            }
        }
        rows = compare_normalized_props(fr_map, fd_only_tier)
        self.assertEqual(len(rows), 2)
        by_key = {row["compare_key"]: row for row in rows}
        half = by_key[ou_key]
        plus = by_key[tier_key]
        self.assertIn("19,5", half["ligne_props_fr"])
        self.assertIn("(US 20+)", half["ligne_props_fr"])
        self.assertTrue(half["marche_fanduel"].startswith("20+ ·"))
        self.assertFalse(half["paire_fd_complete"])
        self.assertIn("20+", plus["ligne_props_fr"])
        self.assertNotIn("(US ", plus["ligne_props_fr"])
        self.assertTrue(plus["marche_fanduel"].startswith("20+ ·"))
        self.assertFalse(plus["paire_fd_complete"])

        fd_ou = {
            ou_key: {
                "market_label": "Anthony Davis - Points",
                "outcomes": {
                    "Over": {"decimal_fr": 1.91, "american": -110},
                    "Under": {"decimal_fr": 1.87, "american": -115},
                },
            }
        }
        paired = compare_normalized_props(
            {tier_key: fr_map[tier_key]},
            fd_ou,
        )
        self.assertEqual(len(paired), 1)
        row = paired[0]
        self.assertTrue(row["paire_fd_complete"])
        self.assertIn("20+", row["ligne_props_fr"])
        self.assertIn("(US 19,5)", row["ligne_props_fr"])
        self.assertTrue(row["marche_fanduel"].startswith("19,5 ·"))
        self.assertEqual(row["issue_fr_contraire"], "Moins 19,5")
        self.assertEqual(row["fanduel_compare_key"], ou_key)


if __name__ == "__main__":
    unittest.main()
