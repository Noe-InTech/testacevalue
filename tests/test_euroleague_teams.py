"""Appariement Euroleague : Hapoel n'est pas Maccabi, Paris = Paris Basketball."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from basketball_schedule import filter_nba_listings_by_hours, normalize_euroleague_hours
from euroleague_teams import (
    canonical_euroleague_club,
    euroleague_teams_match,
    split_euroleague_clubs,
)
from unibet_basketball_client import UnibetBasketballClient


class EuroleagueTeamTests(unittest.TestCase):
    def test_hapoel_is_not_maccabi(self) -> None:
        self.assertEqual(canonical_euroleague_club("Hapoel Tel-Aviv"), "Hapoel Tel Aviv")
        self.assertEqual(canonical_euroleague_club("Maccabi Tel-Aviv"), "Maccabi Tel Aviv")
        self.assertFalse(
            euroleague_teams_match(
                "Hapoel Tel-Aviv",
                "Virtus Bologna",
                "Maccabi Tel-Aviv",
                "Virtus Bologna",
            )
        )

    def test_cross_book_names(self) -> None:
        self.assertTrue(
            euroleague_teams_match(
                "Paris Basketball",
                "Valencia Basket",
                "Paris",
                "Valence",
            )
        )
        self.assertTrue(
            euroleague_teams_match(
                "FC Barcelona",
                "Olimpia Milano",
                "Barcelone",
                "EA7 Emporio Milano",
            )
        )
        self.assertTrue(
            euroleague_teams_match(
                "KK Crvena zvezda Belgrade",
                "KK Partizan Belgrade",
                "Etoile Rouge Belgrade",
                "Partizan",
            )
        )
        self.assertEqual(
            split_euroleague_clubs("armani-milan-barcelone-m1231029751808000"),
            ("Olimpia Milano", "FC Barcelona"),
        )
        self.assertEqual(
            split_euroleague_clubs("bc-zalgiris-kaunas-lyon-villeurbanne-m1"),
            ("Zalgiris Kaunas", "ASVEL"),
        )
        self.assertEqual(
            UnibetBasketballClient._teams_from_euroleague_slug("mac-tel-aviv-vs-real-madrid"),
            ("Maccabi Tel Aviv", "Real Madrid"),
        )
        self.assertEqual(
            UnibetBasketballClient._teams_from_euroleague_slug("er-belgrade-vs-mac-tel-aviv"),
            ("Crvena Zvezda", "Maccabi Tel Aviv"),
        )

    def test_hour_window_keeps_96(self) -> None:
        self.assertEqual(normalize_euroleague_hours(None), 96)
        self.assertEqual(normalize_euroleague_hours(24), 24)
        self.assertEqual(normalize_euroleague_hours(12), 96)
        now = datetime(2026, 10, 21, 17, 0, tzinfo=timezone.utc)
        friday = "2026-10-23T18:45:00.000Z"
        later = "2026-10-27T16:00:00.000Z"
        fd_friday = SimpleNamespace(
            open_date=friday,
            home_team="Paris Basketball",
            away_team="Valencia Basket",
        )
        fd_next = SimpleNamespace(
            open_date=later,
            home_team="Dubai Basketball",
            away_team="Paris Basketball",
        )
        unibet = SimpleNamespace(home_team="Paris", away_team="Valence")
        kept_uni, _bet, _wx, kept_fd, note = filter_nba_listings_by_hours(
            unibet_events=[unibet],
            betclic_links=[],
            winamax_links=[],
            fanduel_events=[fd_friday, fd_next],
            hours=96,
            teams_match=euroleague_teams_match,
            normalize=normalize_euroleague_hours,
            label="Euroleague",
            now=now,
        )
        self.assertEqual(len(kept_fd), 1)
        self.assertEqual(kept_fd[0].home_team, "Paris Basketball")
        self.assertEqual(len(kept_uni), 1)
        self.assertIn("Euroleague 96h", note or "")
        self.assertLess(now + timedelta(hours=96), datetime(2026, 10, 27, 16, 0, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
