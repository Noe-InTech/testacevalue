import unittest

from basketball_books_mapping import normalize_unibet_market
from unibet_basketball_client import UnibetBasketballClient


class UnibetBasketballOuTests(unittest.TestCase):
    def test_parse_ou_outcomes_plus_de_format(self) -> None:
        chunk = (
            '"marketDesc":"Plus / Moins rebonds - Jordin Canada - Match",'
            '"description":"Plus de 4,5","price":"1.95",'
            '"description":"Moins de 4,5","price":"1.50"'
        )
        outcomes = UnibetBasketballClient()._parse_ou_outcomes(chunk)
        self.assertEqual(len(outcomes), 2)
        by_label = {item.label: item.odds for item in outcomes}
        self.assertEqual(by_label["Plus de 4,5"], 1.95)
        self.assertEqual(by_label["Moins de 4,5"], 1.5)

    def test_parse_ou_outcomes_rejects_duplicate_prices(self) -> None:
        chunk = (
            '"description":"Plus 4.5","price":"1.95",'
            '"description":"Moins 4.5","price":"1.95"'
        )
        outcomes = UnibetBasketballClient()._parse_ou_outcomes(chunk)
        self.assertEqual(outcomes, [])

    def test_normalize_unibet_rebounds_canada(self) -> None:
        markets = normalize_unibet_market(
            "Plus / Moins rebonds - Jordin Canada - Match",
            [("Plus de 4,5", 1.95), ("Moins de 4,5", 1.5)],
            ["Jordin Canada"],
        )
        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0].compare_key, "rebounds_player|canada|4.5")
        odds = {item.label: item.odds for item in markets[0].outcomes}
        self.assertEqual(odds["Over"], 1.95)
        self.assertEqual(odds["Under"], 1.5)


if __name__ == "__main__":
    unittest.main()
