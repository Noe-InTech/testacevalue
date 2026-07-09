import unittest

from compare_markets import (
    build_pinnacle_outcome_entries,
    display_team,
    map_pinnacle_guest_market_to_compare_key,
    normalize_point_str,
    normalize_team,
)
from market_mapping import coteur_outcome_label, map_coteur_to_pinnacle
from markets import collect_allowed_markets, is_allowed_market
from fanduel_client import american_to_decimal_fr, format_american_moneyline, format_french_decimal
from scrape_pinnacle import american_to_decimal, outcome_label, period_label


class TeamNormalizationTests(unittest.TestCase):
    def test_normalize_team_aliases(self) -> None:
        self.assertEqual(normalize_team("MAROC"), "morocco")
        self.assertEqual(normalize_team("Etats-Unis"), "united states")
        self.assertEqual(normalize_team("Cote d'Ivoire"), "ivory coast")

    def test_display_team_keeps_french_case(self) -> None:
        self.assertEqual(display_team("MAROC"), "Maroc")
        self.assertEqual(display_team("FRANCE"), "France")
        self.assertEqual(display_team("Belgique"), "Belgique")


class MarketFilterTests(unittest.TestCase):
    def test_is_allowed_market_excludes_handicaps_and_exact_scores(self) -> None:
        self.assertFalse(is_allowed_market("spreads"))
        self.assertFalse(is_allowed_market("alternate_spreads"))
        self.assertFalse(is_allowed_market("correct_score"))
        self.assertFalse(is_allowed_market("correct_score_h1"))
        self.assertFalse(is_allowed_market("h2h_lay"))
        self.assertTrue(is_allowed_market("h2h"))
        self.assertTrue(is_allowed_market("totals_h1"))

    def test_collect_allowed_markets_filters_target_bookmaker(self) -> None:
        payload = {
            "bookmakers": [
                {
                    "key": "pinnacle",
                    "markets": [
                        {"key": "h2h"},
                        {"key": "spreads"},
                        {"key": "totals"},
                    ],
                },
                {
                    "key": "other",
                    "markets": [{"key": "draw_no_bet"}],
                },
            ]
        }
        self.assertEqual(collect_allowed_markets(payload), ["h2h", "totals"])


class MarketMappingTests(unittest.TestCase):
    def test_map_coteur_to_pinnacle_keeps_lines(self) -> None:
        self.assertEqual(map_coteur_to_pinnacle("OU", "2-5"), "totals|2.5")
        self.assertEqual(map_coteur_to_pinnacle("HTOU", "1-5"), "totals_h1|1.5")
        self.assertEqual(map_coteur_to_pinnacle("1n2", ""), "h2h")
        self.assertIsNone(map_coteur_to_pinnacle("12", ""))

    def test_coteur_outcome_labels_are_normalized(self) -> None:
        self.assertEqual(coteur_outcome_label("1n2", "0", "France", "Maroc"), "Nul")
        self.assertEqual(coteur_outcome_label("1n2", "1", "France", "Maroc"), "France")
        self.assertEqual(coteur_outcome_label("HT", "2", "France", "Maroc"), "Nul")
        self.assertEqual(coteur_outcome_label("HT", "3", "France", "Maroc"), "Maroc")
        self.assertEqual(coteur_outcome_label("OU", "2", "France", "Maroc"), "Under")
        self.assertEqual(coteur_outcome_label("OU", "3", "France", "Maroc"), "Over")
        self.assertEqual(coteur_outcome_label("HTOU", "2", "France", "Maroc"), "Under")
        self.assertEqual(coteur_outcome_label("HTOU", "3", "France", "Maroc"), "Over")
        self.assertEqual(coteur_outcome_label("BTTS", "1", "France", "Maroc"), "Oui")
        self.assertEqual(
            coteur_outcome_label("HTFT", "5", "France", "Maroc"),
            "Nul/Nul",
        )

    def test_pinnacle_guest_market_keys_are_normalized(self) -> None:
        self.assertEqual(
            map_pinnacle_guest_market_to_compare_key(
                {"market_group_label": "1X2", "period": 0, "prices": []}
            ),
            "h2h",
        )
        self.assertEqual(
            map_pinnacle_guest_market_to_compare_key(
                {
                    "market_group_label": "Over/Under",
                    "period": 1,
                    "prices": [{"points": 1.5}],
                }
            ),
            "totals_h1|1.5",
        )
        self.assertEqual(
            map_pinnacle_guest_market_to_compare_key(
                {
                    "market_group_label": "Over/Under",
                    "period": 0,
                    "prices": [{"points": 2.0}],
                }
            ),
            "totals|2",
        )
        self.assertEqual(
            map_pinnacle_guest_market_to_compare_key(
                {"market_group_label": "Both Teams To Score?", "period": 0, "prices": []}
            ),
            "btts",
        )
        self.assertEqual(
            map_pinnacle_guest_market_to_compare_key(
                {"market_group_label": "3-Way Handicap France +1", "period": 0, "prices": []}
            ),
            None,
        )
        self.assertEqual(
            map_pinnacle_guest_market_to_compare_key(
                {"market_group_label": "Double Chance 1st Half", "period": 1, "prices": []}
            ),
            "double_chance_h1",
        )


class PinnacleGuestScrapeTests(unittest.TestCase):
    def test_american_to_decimal(self) -> None:
        self.assertEqual(american_to_decimal(150), 2.5)
        self.assertEqual(american_to_decimal(-200), 1.5)
        self.assertIsNone(american_to_decimal(None))

    def test_american_to_decimal_fr(self) -> None:
        self.assertEqual(american_to_decimal_fr(150), 2.5)
        self.assertEqual(american_to_decimal_fr(-200), 1.5)
        self.assertEqual(american_to_decimal_fr(-108), 1.93)
        self.assertEqual(american_to_decimal_fr(-110), 1.91)

    def test_fanduel_french_formats(self) -> None:
        self.assertEqual(format_american_moneyline(-108), "-108")
        self.assertEqual(format_american_moneyline(150), "+150")
        self.assertEqual(format_french_decimal(1.7), "1,70")
        self.assertEqual(format_french_decimal(1.93), "1,93")

    def test_period_label(self) -> None:
        self.assertEqual(period_label(0), "Match")
        self.assertEqual(period_label(1), "1re mi-temps")
        self.assertEqual(period_label(8), "Qualification")

    def test_normalize_point_str(self) -> None:
        self.assertEqual(normalize_point_str("2.0"), "2")
        self.assertEqual(normalize_point_str("2.5"), "2.5")

    def test_outcome_label(self) -> None:
        matchup = {"participants": [], "side": "home"}
        self.assertEqual(
            outcome_label({"designation": "home"}, matchup, "France", "Morocco"),
            "France",
        )
        self.assertEqual(
            outcome_label({"designation": "draw"}, matchup, "France", "Morocco"),
            "Nul",
        )
        self.assertEqual(
            outcome_label({"designation": "over"}, matchup, "France", "Morocco"),
            "France Over",
        )

    def test_build_pinnacle_outcome_entries_normalizes_specials(self) -> None:
        event = {"home_team": "France", "away_team": "Morocco"}
        dc_market = {
            "description": "Double Chance",
            "variant_label": "Double Chance",
            "prices": [
                {"outcome": "France Or Draw", "decimal_odds": 1.12},
                {"outcome": "Draw Or Morocco", "decimal_odds": 2.4},
                {"outcome": "France Or Morocco", "decimal_odds": 1.27},
            ],
        }
        labels = [item["label"] for item in build_pinnacle_outcome_entries("double_chance", dc_market, event)]
        self.assertEqual(labels, ["France ou Nul", "Morocco ou Nul", "France ou Morocco"])

        htft_market = {
            "description": "Half-Time/Full-Time",
            "variant_label": "Half-Time/Full-Time",
            "prices": [{"outcome": "France - Draw", "decimal_odds": 16.35}],
        }
        labels = [item["label"] for item in build_pinnacle_outcome_entries("halftime_fulltime", htft_market, event)]
        self.assertEqual(labels, ["France/Nul"])

        scorer_market = {
            "description": "Kylian Mbappe To Score",
            "variant_label": "Kylian Mbappe To Score",
            "prices": [
                {"outcome": "Yes", "decimal_odds": 1.8},
                {"outcome": "No", "decimal_odds": 1.2},
            ],
        }
        labels = [item["label"] for item in build_pinnacle_outcome_entries("player_goal_scorer_anytime", scorer_market, event)]
        self.assertEqual(labels, ["Kylian Mbappe"])


if __name__ == "__main__":
    unittest.main()
