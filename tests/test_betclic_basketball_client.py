import unittest

from betclic_basketball_client import BetclicBasketballClient
from betclic_client import BetclicClient


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

    def test_collect_outcomes_prefers_betslip_player_name(self) -> None:
        market = {
            "id": "1256942198603780",
            "mainSelections": [
                {
                    "id": "1256942223765653",
                    "name": "+ de 16,5",
                    "betslipName": "Jayson Tatum + de 16,5",
                    "odds": 1.04,
                    "status": 1,
                    "betslipMarketId": "1256942198603780",
                },
                {
                    "id": "1256942223765654",
                    "name": "+ de 16,5",
                    "betslipName": "Cade Cunningham + de 16,5",
                    "odds": 1.05,
                    "status": 1,
                    "betslipMarketId": "1256942198603780",
                },
            ],
        }
        outcomes = BetclicClient._collect_market_outcomes(market)
        self.assertEqual(len(outcomes), 2)
        self.assertEqual(outcomes[0].label, "Jayson Tatum + de 16,5")
        self.assertEqual(outcomes[1].label, "Cade Cunningham + de 16,5")


if __name__ == "__main__":
    unittest.main()
