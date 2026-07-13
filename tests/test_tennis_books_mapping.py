import unittest

from tennis_books_mapping import (
    is_advanced_compare_key,
    normalize_betclic_market,
    normalize_unibet_market,
    normalize_winamax_market,
    normalize_ou_label,
    parse_french_number,
)


class TennisBooksMappingTests(unittest.TestCase):
    def test_parse_french_number(self) -> None:
        self.assertEqual(parse_french_number("Plus 5,5"), 5.5)
        self.assertEqual(parse_french_number("+ de 34,5"), 34.5)

    def test_normalize_ou_label(self) -> None:
        self.assertEqual(normalize_ou_label("Plus 5,5"), "Over")
        self.assertEqual(normalize_ou_label("- de 34,5"), "Under")
        self.assertEqual(normalize_ou_label("J.Sinner se fait breaker"), "Break")

    def test_normalize_unibet_breaks_total(self) -> None:
        markets = normalize_unibet_market(
            "Plus / Moins Breaks - Match",
            [("Plus 5,5", 2.05), ("Moins 5,5", 1.45)],
            "Jannik Sinner",
            "Novak Djokovic",
        )
        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0].compare_key, "breaks_total|5.5")
        self.assertEqual(markets[0].outcomes[0].label, "Over")
        self.assertTrue(is_advanced_compare_key(markets[0].compare_key))

    def test_normalize_unibet_breaks_player(self) -> None:
        markets = normalize_unibet_market(
            "Plus / Moins 3,5 Break(s) - J.Sinner - Match",
            [("Plus 3,5", 1.7), ("Moins 3,5", 1.7)],
            "Jannik Sinner",
            "Novak Djokovic",
        )
        self.assertEqual(markets[0].compare_key, "breaks_player|sinner|3.5")
        self.assertEqual(markets[0].player_name, "Jannik Sinner")

    def test_normalize_unibet_first_break(self) -> None:
        markets = normalize_unibet_market(
            "1er joueur à réussir un break - Match",
            [("J.Sinner", 1.3), ("N.Djokovic", 2.5)],
            "Jannik Sinner",
            "Novak Djokovic",
        )
        self.assertEqual(markets[0].compare_key, "first_break")
        self.assertEqual(set(item.label for item in markets[0].outcomes), {"Jannik Sinner", "Novak Djokovic"})

    def test_normalize_unibet_tie_break_match(self) -> None:
        markets = normalize_unibet_market(
            "Plus / Moins tie-break - Match",
            [("Plus 0,5", 1.35), ("Moins 0,5", 2.45), ("Plus 1,5", 3.5), ("Moins 1,5", 1.15)],
            "Jannik Sinner",
            "Novak Djokovic",
        )
        keys = {market.compare_key for market in markets}
        self.assertIn("tie_break_match|0.5", keys)
        self.assertIn("tie_break_match|1.5", keys)

    def test_normalize_betclic_games_total(self) -> None:
        markets = normalize_betclic_market(
            "Nombre total de jeux",
            [("+ de 34,5", 1.42), ("- de 34,5", 2.1)],
            "Jannik Sinner",
            "Novak Djokovic",
        )
        self.assertEqual(markets[0].compare_key, "games_total|34.5")

    def test_normalize_unibet_h2h(self) -> None:
        markets = normalize_unibet_market(
            "Face à Face - Match",
            [("J.Sinner", 1.21), ("N.Djokovic", 4.6)],
            "Jannik Sinner",
            "Novak Djokovic",
        )
        self.assertEqual(markets[0].compare_key, "h2h")

    def test_normalize_unibet_games_total(self) -> None:
        markets = normalize_unibet_market(
            "Plus / Moins Jeux - Match",
            [("Plus 34,5", 1.42), ("Moins 34,5", 2.1)],
            "Jannik Sinner",
            "Novak Djokovic",
        )
        self.assertEqual(markets[0].compare_key, "games_total|34.5")

    def test_normalize_betclic_h2h(self) -> None:
        markets = normalize_betclic_market(
            "Vainqueur du match",
            [("Jannik Sinner", 1.21), ("Novak Djokovic", 4.6)],
            "Jannik Sinner",
            "Novak Djokovic",
        )
        self.assertEqual(markets[0].compare_key, "h2h")

    def test_normalize_winamax_h2h(self) -> None:
        markets = normalize_winamax_market(
            "Vainqueur",
            [("J. Sinner", 1.21), ("N. Djokovic", 4.6)],
            "Jannik Sinner",
            "Novak Djokovic",
        )
        self.assertEqual(markets[0].compare_key, "h2h")

    def test_normalize_winamax_games_total(self) -> None:
        markets = normalize_winamax_market(
            "Nombre de jeux (34.5)",
            [("Plus de 34,5", 1.47), ("Moins de 34,5", 2.2)],
            "Jannik Sinner",
            "Novak Djokovic",
        )
        self.assertEqual(markets[0].compare_key, "games_total|34.5")

    def test_normalize_winamax_breaks_total(self) -> None:
        markets = normalize_winamax_market(
            "Nombre de breaks dans le match (5.5)",
            [("Plus de 5,5 breaks", 1.8), ("Moins de 5,5 breaks", 1.7)],
            "Jannik Sinner",
            "Novak Djokovic",
        )
        self.assertEqual(markets[0].compare_key, "breaks_total|5.5")
        self.assertTrue(is_advanced_compare_key(markets[0].compare_key))

    def test_normalize_winamax_first_break(self) -> None:
        markets = normalize_winamax_market(
            "Premier joueur à réaliser un break",
            [("J. Sinner", 1.3), ("N. Djokovic", 2.9)],
            "Jannik Sinner",
            "Novak Djokovic",
        )
        self.assertEqual(markets[0].compare_key, "first_break")

    def test_normalize_winamax_tie_break_match(self) -> None:
        markets = normalize_winamax_market(
            "Nombre de tie-breaks (1.5)",
            [("Plus de 1,5", 2.1), ("Moins de 1,5", 1.65)],
            "Jannik Sinner",
            "Novak Djokovic",
        )
        self.assertEqual(markets[0].compare_key, "tie_break_match|1.5")

    def test_normalize_winamax_tie_break_set(self) -> None:
        markets = normalize_winamax_market(
            "Tie-break (1er set)",
            [("Oui", 1.9), ("Non", 1.85)],
            "Jannik Sinner",
            "Novak Djokovic",
        )
        self.assertEqual(markets[0].compare_key, "tie_break_set|1")
        self.assertEqual(set(item.label for item in markets[0].outcomes), {"Oui", "Non"})

    def test_normalize_winamax_breaks_player(self) -> None:
        markets = normalize_winamax_market(
            "Nombre de breaks de J. Sinner (3.5)",
            [("Plus de 3,5 breaks", 1.7), ("Moins de 3,5 breaks", 1.9)],
            "Jannik Sinner",
            "Novak Djokovic",
        )
        self.assertEqual(markets[0].compare_key, "breaks_player|sinner|3.5")

    def test_normalize_betclic_breaks_total(self) -> None:
        markets = normalize_betclic_market(
            "Nombre total de breaks",
            [("+ de 5,5", 1.8), ("- de 5,5", 1.9)],
            "Jannik Sinner",
            "Novak Djokovic",
        )
        self.assertEqual(markets[0].compare_key, "breaks_total|5.5")

    def test_normalize_betclic_first_break(self) -> None:
        markets = normalize_betclic_market(
            "Premier joueur à réaliser un break",
            [("Jannik Sinner", 1.4), ("Novak Djokovic", 2.8)],
            "Jannik Sinner",
            "Novak Djokovic",
        )
        self.assertEqual(markets[0].compare_key, "first_break")

    def test_normalize_betclic_tie_break_set(self) -> None:
        markets = normalize_betclic_market(
            "Tie-break - 1er Set",
            [("Oui", 1.88), ("Non", 1.87)],
            "Jannik Sinner",
            "Novak Djokovic",
        )
        self.assertEqual(markets[0].compare_key, "tie_break_set|1")

    def test_normalize_unibet_tie_break_set(self) -> None:
        markets = normalize_unibet_market(
            "Tie-break - 1er Set",
            [("Oui", 1.9), ("Non", 1.85)],
            "Jannik Sinner",
            "Novak Djokovic",
        )
        self.assertEqual(markets[0].compare_key, "tie_break_set|1")

    def test_normalize_unibet_match_tiebreak_yes_no(self) -> None:
        markets = normalize_unibet_market(
            "Y aura-t-il au moins un Tie-break - Match",
            [("Oui", 1.55), ("Non", 2.35)],
            "Jannik Sinner",
            "Novak Djokovic",
        )
        self.assertEqual(markets[0].compare_key, "tie_break_match|0.5")
        self.assertEqual(set(item.label for item in markets[0].outcomes), {"Over", "Under"})

    def test_normalize_winamax_match_tiebreak_yes_no(self) -> None:
        markets = normalize_winamax_market(
            "Tie-break au cours du match",
            [("Oui", 1.6), ("Non", 2.2)],
            "Jannik Sinner",
            "Novak Djokovic",
        )
        self.assertEqual(markets[0].compare_key, "tie_break_match|0.5")
        self.assertEqual(set(item.label for item in markets[0].outcomes), {"Over", "Under"})


if __name__ == "__main__":
    unittest.main()
