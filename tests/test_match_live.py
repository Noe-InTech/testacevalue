import unittest

from match_live import event_is_live, mark_anchor_live, stamp_rows_live, unibet_url_is_live


class MatchLiveTests(unittest.TestCase):
    def test_unibet_live_url(self) -> None:
        self.assertTrue(unibet_url_is_live("https://www.unibet.fr/paris-en-direct/1/foo"))
        self.assertFalse(unibet_url_is_live("https://www.unibet.fr/paris-tennis/1/match"))

    def test_event_is_live_sources(self) -> None:
        self.assertTrue(event_is_live(status="LIVE"))
        self.assertTrue(event_is_live(is_live=True))
        self.assertTrue(event_is_live(url="https://www.unibet.fr/paris-en-direct/9/x"))
        self.assertFalse(event_is_live(status="PREMATCH"))

    def test_mark_and_stamp(self) -> None:
        anchor: dict = {"is_live": False}
        mark_anchor_live(anchor, True)
        self.assertTrue(anchor["is_live"])
        rows = [{"match": "A vs B"}, {"match": "C vs D"}]
        stamp_rows_live(rows, True)
        self.assertTrue(all(row["is_live"] for row in rows))


if __name__ == "__main__":
    unittest.main()
