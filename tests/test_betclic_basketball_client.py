import unittest

from betclic_basketball_client import BetclicBasketballClient


class BetclicBasketballClientTests(unittest.TestCase):
    def test_nba_slug_without_vs_separator(self) -> None:
        home, away = BetclicBasketballClient._teams_from_nba_slug(
            "detroit-pistons-boston-celtics-m1195396246274048",
        )
        self.assertEqual(home, "Detroit Pistons")
        self.assertEqual(away, "Boston Celtics")

    def test_wnba_slug_valkyries_dream(self) -> None:
        home, away = BetclicBasketballClient._teams_from_slug(
            "golden-state-valkyries-atlanta-dream-m1249069969182725",
        )
        self.assertEqual(home, "Golden State Valkyries")
        self.assertEqual(away, "Atlanta Dream")


if __name__ == "__main__":
    unittest.main()
