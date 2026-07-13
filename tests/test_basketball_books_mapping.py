import unittest

from basketball_books_mapping import (
    is_wnba_player_prop_label,
    normalize_betclic_market,
    normalize_winamax_market,
)
from basketball_market_mapping import (
    build_player_prop_key,
    is_comparable_player_prop_key,
    map_fanduel_market_to_compare_key,
)
from scan_tennis_aces import is_breaks_market


class BasketballBooksMappingTests(unittest.TestCase):
    def test_is_wnba_player_prop_label(self) -> None:
        self.assertTrue(
            is_wnba_player_prop_label("Nombre de points du joueur - Allisha Gray (20.5)")
        )
        self.assertTrue(
            is_wnba_player_prop_label(
                "Nombre de points du joueur (paliers) - Allisha Gray (19.5)"
            )
        )
        self.assertTrue(
            is_wnba_player_prop_label(
                "Nombre de paniers à 3 points du joueur - Allisha Gray (1.5)"
            )
        )
        self.assertTrue(is_wnba_player_prop_label("Double-double"))
        self.assertFalse(is_wnba_player_prop_label("Double chance marqueurs - A. Gray (14.5)"))

    def test_normalize_winamax_points_player(self) -> None:
        roster = ["Allisha Gray", "Rhyne Howard"]
        markets = normalize_winamax_market(
            "Nombre de points du joueur - Allisha Gray (20.5)",
            [("Plus de 20,5", 1.8), ("Moins de 20,5", 1.9)],
            roster,
        )
        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0].compare_key, build_player_prop_key("points_player", "Allisha Gray", "20.5"))
        self.assertEqual(set(item.label for item in markets[0].outcomes), {"Over", "Under"})

    def test_normalize_winamax_rebounds_player(self) -> None:
        markets = normalize_winamax_market(
            "Nombre de rebonds du joueur - Rhyne Howard (4.5)",
            [("Plus de 4,5", 1.7), ("Moins de 4,5", 2.0)],
            ["Rhyne Howard"],
        )
        self.assertEqual(markets[0].compare_key, "rebounds_player|howard|4.5")

    def test_normalize_winamax_threes_player(self) -> None:
        markets = normalize_winamax_market(
            "Nombre de paniers à 3 points du joueur - Allisha Gray (1.5)",
            [("Plus de 1,5", 1.6), ("Moins de 1,5", 1.86)],
            ["Allisha Gray"],
        )
        self.assertEqual(markets[0].compare_key, "threes_made_player|gray|1.5")

    def test_normalize_winamax_points_tier(self) -> None:
        markets = normalize_winamax_market(
            "Nombre de points du joueur (paliers) - Allisha Gray (19.5)",
            [("Plus de 19,5", 1.2)],
            ["Allisha Gray"],
        )
        self.assertEqual(markets[0].compare_key, "points_player|gray|19.5")
        self.assertEqual(markets[0].outcomes[0].label, "Over")

    def test_normalize_winamax_double_double(self) -> None:
        markets = normalize_winamax_market(
            "Double-double",
            [("Allisha Gray", 4.5), ("Nneka Ogwumike", 2.25)],
            ["Allisha Gray", "Nneka Ogwumike"],
        )
        self.assertEqual(len(markets), 2)
        self.assertEqual(markets[0].compare_key, "double_double_player|gray|0")

    def test_normalize_betclic_points_plus_moins(self) -> None:
        markets = normalize_betclic_market(
            "Nombre de points du joueur (plus/moins)",
            [
                ("Allisha Gray + de 20,5", 1.69),
                ("Allisha Gray - de 20,5", 1.88),
            ],
            ["Allisha Gray"],
        )
        self.assertEqual(markets[0].compare_key, "points_player|gray|20.5")

    def test_normalize_unibet_points_ou(self) -> None:
        from basketball_books_mapping import normalize_unibet_market

        markets = normalize_unibet_market(
            "Plus / Moins Points - Allisha Gray - Match",
            [("Plus 20.5", 1.65), ("Moins 20.5", 1.8)],
            ["Allisha Gray"],
        )
        self.assertEqual(markets[0].compare_key, "points_player|gray|20.5")

    def test_normalize_unibet_performance_tier(self) -> None:
        from basketball_books_mapping import normalize_unibet_market

        markets = normalize_unibet_market(
            "Performance Joueur-Point(s) - Match",
            [("Allisha Gray 25+", 2.55)],
            ["Allisha Gray"],
        )
        self.assertEqual(markets[0].compare_key, "points_player|gray|24.5")
        self.assertEqual(markets[0].outcomes[0].label, "Over")

    def test_normalize_winamax_pra_shorthand(self) -> None:
        markets = normalize_winamax_market(
            "Total du joueur (points + rebonds + passes) - Jordin Canada (23.5)",
            [("Plus de 23,5", 1.64), ("Moins de 23,5", 1.82)],
            ["Jordin Canada"],
        )
        self.assertEqual(markets[0].compare_key, "pra_player|canada|23.5")

    def test_normalize_winamax_pts_passes_shorthand(self) -> None:
        markets = normalize_winamax_market(
            "Total du joueur (points + passes) - Jordin Canada (19.5)",
            [("Plus de 19,5", 1.66), ("Moins de 19,5", 1.78)],
            ["Jordin Canada"],
        )
        self.assertEqual(markets[0].compare_key, "points_assists_player|canada|19.5")

    def test_tennis_breaks_filter_unchanged(self) -> None:
        self.assertTrue(is_breaks_market("Plus / Moins Breaks - Match"))


class BasketballMarketMappingTests(unittest.TestCase):
    def test_compare_key(self) -> None:
        key = build_player_prop_key("assists_player", "Jordin Canada", "7.5")
        self.assertEqual(key, "assists_player|canada|7.5")
        self.assertTrue(is_comparable_player_prop_key(key))

    def test_map_fanduel_points_player(self) -> None:
        market = {
            "marketName": "Allisha Gray - Points",
            "runners": [
                {"runnerName": "Allisha Gray Over", "handicap": 20.5, "runnerStatus": "ACTIVE"},
                {"runnerName": "Allisha Gray Under", "handicap": 20.5, "runnerStatus": "ACTIVE"},
            ],
        }
        self.assertEqual(
            map_fanduel_market_to_compare_key(market, roster=["Allisha Gray"]),
            "points_player|gray|20.5",
        )

    def test_map_fanduel_pra_player(self) -> None:
        market = {
            "marketName": "Jordin Canada - Pts + Reb + Ast",
            "runners": [
                {"runnerName": "Jordin Canada Over", "handicap": 24.5, "runnerStatus": "ACTIVE"},
            ],
        }
        self.assertEqual(
            map_fanduel_market_to_compare_key(market, roster=["Jordin Canada"]),
            "pra_player|canada|24.5",
        )

    def test_map_fanduel_made_threes(self) -> None:
        market = {
            "marketName": "Allisha Gray - Made Threes",
            "runners": [
                {"runnerName": "Allisha Gray Over", "handicap": 1.5, "runnerStatus": "ACTIVE"},
                {"runnerName": "Allisha Gray Under", "handicap": 1.5, "runnerStatus": "ACTIVE"},
            ],
        }
        self.assertEqual(
            map_fanduel_market_to_compare_key(market, roster=["Allisha Gray"]),
            "threes_made_player|gray|1.5",
        )

    def test_fanduel_runner_outcome(self) -> None:
        from basketball_market_mapping import fanduel_player_prop_runner_outcome

        self.assertEqual(fanduel_player_prop_runner_outcome("Allisha Gray Over"), "Over")
        self.assertEqual(fanduel_player_prop_runner_outcome("Allisha Gray Under"), "Under")


if __name__ == "__main__":
    unittest.main()
