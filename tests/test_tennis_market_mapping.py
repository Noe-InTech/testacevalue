import unittest

from tennis_market_mapping import (
    coteur_handicap_outcome_label,
    extract_total_line_from_market_name,
    fanduel_runner_label,
    map_coteur_to_fanduel,
    map_fanduel_market_to_compare_key,
    players_match,
)
from tennis_books_mapping import normalize_betclic_market


class TennisMarketMappingTests(unittest.TestCase):
    def test_map_coteur_tennis_markets(self) -> None:
        self.assertEqual(map_coteur_to_fanduel("BTTS", ""), "both_win_set")
        self.assertEqual(map_coteur_to_fanduel("OU", "3-5"), "total_sets|3.5")
        self.assertEqual(map_coteur_to_fanduel("OUJ", "22"), "totals|22.5")
        self.assertEqual(map_coteur_to_fanduel("12", "0:+1-5"), "set_handicap|1.5")

    def test_coteur_handicap_outcome_label(self) -> None:
        self.assertEqual(
            coteur_handicap_outcome_label("0:+1-5", "1", "Sinner", "Djokovic"),
            "Djokovic (+1.5)",
        )
        self.assertEqual(
            coteur_handicap_outcome_label("0:+1-5", "2", "Sinner", "Djokovic"),
            "Sinner (-1.5)",
        )
        self.assertEqual(
            coteur_handicap_outcome_label("+1-5:0", "1", "Sinner", "Djokovic"),
            "Sinner (+1.5)",
        )
        self.assertEqual(
            coteur_handicap_outcome_label("+1-5:0", "2", "Sinner", "Djokovic"),
            "Djokovic (-1.5)",
        )

    def test_extract_total_line_uses_last_number(self) -> None:
        self.assertEqual(extract_total_line_from_market_name("Set 1 Total Games Over/Under 10.5"), "10.5")
        self.assertEqual(extract_total_line_from_market_name("Set Handicap -2.5"), "2.5")

    def test_map_fanduel_market_to_compare_key(self) -> None:
        self.assertEqual(
            map_fanduel_market_to_compare_key({"marketName": "Both Players to win a Set (Yes/No)", "runners": []}),
            "both_win_set",
        )
        self.assertEqual(
            map_fanduel_market_to_compare_key({"marketName": "Total Sets 3.5", "runners": []}),
            "total_sets|3.5",
        )
        self.assertEqual(
            map_fanduel_market_to_compare_key(
                {
                    "marketName": "Set 1 Total Games Over/Under 10.5",
                    "runners": [],
                }
            ),
            "set1_totals|10.5",
        )

    def test_fanduel_runner_label(self) -> None:
        self.assertEqual(fanduel_runner_label("both_win_set", "Yes", "Sinner", "Djokovic"), "Oui")
        self.assertEqual(fanduel_runner_label("total_sets|3.5", "Under 3.5", "Sinner", "Djokovic"), "Under")
        self.assertEqual(
            fanduel_runner_label("set_handicap|1.5", "Sinner (-1.5)", "Sinner", "Djokovic"),
            "Sinner (-1.5)",
        )

    def test_players_match_initials_and_compound_names(self) -> None:
        self.assertTrue(players_match("A.Blinkova", "Alina Blinkova"))
        self.assertTrue(players_match("A.Li", "Ann Li"))
        self.assertTrue(players_match("P.CarrenoBusta", "Pablo Carreno Busta"))
        self.assertTrue(players_match("Grammatikopou", "Valentini Grammatikopoulou"))
        self.assertFalse(players_match("J.Sinner", "Carlos Alcaraz"))

    def test_betclic_ace_tier_labels(self) -> None:
        markets = normalize_betclic_market(
            "1er set - Jannik Sinner - Nombre total d'aces",
            [("+ de 5,5", 1.45), ("+ de 6,5", 2.1)],
            "Jannik Sinner",
            "Alexander Zverev",
        )
        self.assertEqual(markets, [])

        markets = normalize_betclic_market(
            "Match - Alexander Zverev - Nombre total d'aces",
            [("+ de 14,5", 1.8), ("+ de 15,5", 2.0)],
            "Jannik Sinner",
            "Alexander Zverev",
        )
        self.assertEqual(len(markets), 2)
        self.assertEqual(markets[0].compare_key, "aces_player|zverev|14.5")
        self.assertEqual(markets[0].outcomes[0].label, "Over")


if __name__ == "__main__":
    unittest.main()
