import unittest
from datetime import datetime, timezone

from compare_tennis_aces_vs_fanduel import _count_live_anchors
from fanduel_client import FanDuelClient
from winamax_client import WinamaxMatchLink


class LiveAnchorCountTests(unittest.TestCase):
    def test_count_live_anchors(self) -> None:
        anchors = [
            {"home_player": "J.Sinner", "away_player": "A.Zverev", "name": "x"},
            {"home_player": "L.Sonego", "away_player": "J.Schwaerzler", "name": "y"},
        ]
        unibet = [
            {
                "home": "J.Sinner",
                "away": "A.Zverev",
                "url": "https://x/paris-en-direct/1/a",
                "is_live": True,
            },
            {
                "home": "L.Sonego",
                "away": "J.Schwaerzler",
                "url": "https://x/paris-tennis/atp/gstaad-h/1/a",
                "is_live": False,
            },
        ]
        winamax: list[WinamaxMatchLink] = []
        self.assertEqual(_count_live_anchors(anchors, unibet, winamax), 1)

    def test_fanduel_event_started(self) -> None:
        now = datetime(2026, 7, 12, 18, 0, tzinfo=timezone.utc)
        self.assertTrue(
            FanDuelClient._event_started("2026-07-12T14:42:00.000Z", now=now)
        )
        self.assertFalse(
            FanDuelClient._event_started("2026-07-12T20:00:00.000Z", now=now)
        )


if __name__ == "__main__":
    unittest.main()
