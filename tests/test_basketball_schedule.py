"""Filtre horaire NBA (12 / 24 / 48 h)."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from basketball_schedule import (
    filter_nba_listings_by_hours,
    normalize_nba_hours,
    parse_basketball_start,
)


def _teams_match(home_a: str, away_a: str, home_b: str, away_b: str) -> bool:
    return home_a.lower() == home_b.lower() and away_a.lower() == away_b.lower()


class BasketballScheduleTests(unittest.TestCase):
    def test_normalize_nba_hours(self) -> None:
        self.assertEqual(normalize_nba_hours(None), 12)
        self.assertEqual(normalize_nba_hours(24), 24)
        self.assertEqual(normalize_nba_hours(99), 12)

    def test_parse_basketball_start_iso_and_ms(self) -> None:
        dt = parse_basketball_start("2026-10-21T23:30:00.000Z")
        self.assertIsNotNone(dt)
        assert dt is not None
        self.assertEqual(dt.year, 2026)
        ms = int(dt.timestamp() * 1000)
        self.assertEqual(parse_basketball_start(ms), dt)

    def test_filter_listings_keeps_in_window_fd_and_aligned_fr(self) -> None:
        now = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
        soon = (now + timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        later = (now + timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        fd_soon = SimpleNamespace(
            event_id="1",
            home_team="Miami Heat",
            away_team="Minnesota Timberwolves",
            open_date=soon,
        )
        fd_later = SimpleNamespace(
            event_id="2",
            home_team="Los Angeles Lakers",
            away_team="Golden State Warriors",
            open_date=later,
        )
        uni_soon = SimpleNamespace(home_team="Miami Heat", away_team="Minnesota Timberwolves")
        uni_later = SimpleNamespace(home_team="Los Angeles Lakers", away_team="Golden State Warriors")
        uni, bet, wx, fd, note = filter_nba_listings_by_hours(
            unibet_events=[uni_soon, uni_later],
            betclic_links=[],
            winamax_links=[],
            fanduel_events=[fd_soon, fd_later],
            hours=12,
            teams_match=_teams_match,
            now=now,
        )
        self.assertEqual(len(fd), 1)
        self.assertEqual(fd[0].event_id, "1")
        self.assertEqual(len(uni), 1)
        self.assertEqual(uni[0].home_team, "Miami Heat")
        self.assertIn("12h", note or "")


if __name__ == "__main__":
    unittest.main()
