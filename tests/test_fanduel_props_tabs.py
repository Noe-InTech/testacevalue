import unittest

from fanduel_client import ACES_EVENT_TABS, EVENT_TABS, FANDUEL_PROPS_TABS, merge_event_market_payloads


class FanDuelPropsTabsTests(unittest.TestCase):
    def test_props_tabs_include_set_betting(self) -> None:
        self.assertIn("set-betting", ACES_EVENT_TABS)
        self.assertIn("set-betting", FANDUEL_PROPS_TABS)
        self.assertEqual(FANDUEL_PROPS_TABS, EVENT_TABS)

    def test_merge_event_market_payloads_dedupes_market_ids(self) -> None:
        base = {
            "event_id": "1",
            "markets": [
                {
                    "marketId": "m1",
                    "marketName": "Set 3 Aces",
                    "runners": [{"selectionId": 1, "runnerName": "7+"}],
                }
            ],
        }
        extra = {
            "markets": [
                {
                    "marketId": "m1",
                    "marketName": "Set 3 Aces",
                    "runners": [{"selectionId": 2, "runnerName": "8+"}],
                },
                {
                    "marketId": "m2",
                    "marketName": "Total Tie Breaks 1.5",
                    "runners": [{"selectionId": 3, "runnerName": "Over 1.5"}],
                },
            ]
        }
        merged = merge_event_market_payloads(base, extra)
        self.assertEqual(len(merged["markets"]), 2)
        runners = merged["markets"][0]["runners"]
        self.assertEqual(len(runners), 2)


if __name__ == "__main__":
    unittest.main()
