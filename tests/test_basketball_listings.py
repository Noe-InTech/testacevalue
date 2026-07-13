import unittest

from basketball_listings import is_basketball_outright_slug, is_fanduel_nba_game_event


class BasketballListingsTests(unittest.TestCase):
    def test_outright_slug_detection(self) -> None:
        self.assertTrue(is_basketball_outright_slug("nba-26-27"))
        self.assertTrue(is_basketball_outright_slug("nba-2026-2027"))
        self.assertFalse(is_basketball_outright_slug("los-angeles-lakers-vs-boston-celtics"))

    def test_fanduel_nba_game_event(self) -> None:
        self.assertTrue(is_fanduel_nba_game_event("Toronto Raptors @ Indiana Pacers"))
        self.assertFalse(is_fanduel_nba_game_event("NBA Futures"))
        self.assertFalse(is_fanduel_nba_game_event("NBA Player Awards"))
        self.assertFalse(
            is_fanduel_nba_game_event("Cleveland Cavaliers (HORNET) @ Phoenix Suns (STARFIRE)")
        )


if __name__ == "__main__":
    unittest.main()
