"""Tests merge US odds + mapping Bet365 US + soft-fail runner US."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bet365_us_client import fetch_bet365_us_normalized_map
from bet365_us_mapping import (
    build_normalized_map_from_bet365_markets,
    map_bet365_tennis_market_to_compare_key,
)
from us_odds_merge import merge_best_us_odds_maps, outcome_us_source_fields, tag_us_market_map
from us_runner_client import fetch_bet365_us_map, merge_us_map_with_bet365


class UsOddsMergeTests(unittest.TestCase):
    def test_merge_picks_higher_decimal_per_outcome(self) -> None:
        fd = tag_us_market_map(
            {
                "aces_total|10.5": {
                    "compare_key": "aces_total|10.5",
                    "market_label": "Total Aces 10.5",
                    "outcomes": {
                        "Over": {"american": -110, "decimal_fr": 1.91, "decimal_raw": 1.91},
                        "Under": {"american": -110, "decimal_fr": 1.91, "decimal_raw": 1.91},
                    },
                }
            },
            source="fanduel",
        )
        b365 = tag_us_market_map(
            {
                "aces_total|10.5": {
                    "compare_key": "aces_total|10.5",
                    "market_label": "Total Aces 10.5",
                    "outcomes": {
                        "Over": {"american": 105, "decimal_fr": 2.05, "decimal_raw": 2.05},
                        "Under": {"american": -125, "decimal_fr": 1.8, "decimal_raw": 1.8},
                    },
                }
            },
            source="bet365",
        )
        merged = merge_best_us_odds_maps(fd, b365)
        over = merged["aces_total|10.5"]["outcomes"]["Over"]
        under = merged["aces_total|10.5"]["outcomes"]["Under"]
        self.assertEqual(over["decimal_fr"], 2.05)
        self.assertEqual(over["us_source"], "bet365")
        self.assertEqual(under["decimal_fr"], 1.91)
        self.assertEqual(under["us_source"], "fanduel")
        fields = outcome_us_source_fields(merged["aces_total|10.5"], "Over")
        self.assertEqual(fields["us_source_label"], "Bet365 US")


class Bet365MappingTests(unittest.TestCase):
    def test_map_tennis_aces_and_breaks(self) -> None:
        home, away = "Jannik Sinner", "Carlos Alcaraz"
        self.assertEqual(
            map_bet365_tennis_market_to_compare_key("Total Aces 12.5", home, away),
            "aces_total|12.5",
        )
        key = map_bet365_tennis_market_to_compare_key("Total Jannik Sinner Aces 8.5", home, away)
        self.assertIsNotNone(key)
        assert key is not None
        self.assertTrue(key.startswith("aces_player|"))
        self.assertTrue(key.endswith("|8.5"))
        self.assertEqual(
            map_bet365_tennis_market_to_compare_key("Total Breaks 3.5", home, away),
            "breaks_total|3.5",
        )

    def test_build_map_from_markets(self) -> None:
        markets = [
            {
                "market_name": "Total Aces 10.5",
                "runners": [
                    {"name": "Over", "american": 100},
                    {"name": "Under", "american": -120},
                ],
            }
        ]
        variant = build_normalized_map_from_bet365_markets(
            markets,
            sport="tennis",
            home="A",
            away="B",
            families={"aces"},
        )
        self.assertIn("aces_total|10.5", variant)
        self.assertIn("Over", variant["aces_total|10.5"]["outcomes"])

    def test_fixture_client(self) -> None:
        payload = {
            "markets": [
                {
                    "market_name": "Total Breaks 2.5",
                    "runners": [
                        {"name": "Over", "decimal": 1.95},
                        {"name": "Under", "decimal": 1.85},
                    ],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "b365.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = fetch_bet365_us_normalized_map(
                sport="tennis",
                home="A",
                away="B",
                families={"breaks"},
                fixture_path=path,
            )
        self.assertTrue(result["ok"])
        self.assertFalse(result["soft_fail"])
        self.assertIn("breaks_total|2.5", result["map"])
        self.assertEqual(result["map"]["breaks_total|2.5"]["source"], "bet365")


class UsRunnerClientTests(unittest.TestCase):
    def test_soft_fail_when_not_configured(self) -> None:
        with mock.patch.dict("os.environ", {"US_RUNNER_URL": "", "US_RUNNER_SECRET": ""}, clear=False):
            result = fetch_bet365_us_map(sport="tennis", home="A", away="B")
        self.assertTrue(result["soft_fail"])
        self.assertEqual(result["map"], {})

    def test_merge_soft_fail_keeps_fanduel(self) -> None:
        fd = {
            "aces_total|5.5": {
                "compare_key": "aces_total|5.5",
                "market_label": "Total Aces 5.5",
                "outcomes": {
                    "Over": {"american": -105, "decimal_fr": 1.95, "decimal_raw": 1.95},
                },
            }
        }
        with mock.patch(
            "us_runner_client.fetch_bet365_us_map",
            return_value={"ok": False, "soft_fail": True, "message": "down", "map": {}},
        ):
            merged, meta = merge_us_map_with_bet365(
                fd,
                sport="tennis",
                home="A",
                away="B",
                families=["aces"],
            )
        self.assertTrue(meta["soft_fail"])
        self.assertEqual(merged["aces_total|5.5"]["outcomes"]["Over"]["decimal_fr"], 1.95)
        self.assertEqual(merged["aces_total|5.5"]["source"], "fanduel")


class BaseballOverlayBestOddsTests(unittest.TestCase):
    def test_overlay_picks_better_rotowire_outcome(self) -> None:
        from baseball_market_mapping import build_runs_player_key
        from compare_baseball_vs_fanduel import overlay_us_reference_map
        from rotowire_mlb_props_client import RotoWireRunsRow

        key = build_runs_player_key("CJ Abrams", 1)
        # FanDuel Yes worse than RotoWire Yes → RW wins Yes; FD still can win No if better.
        merged = overlay_us_reference_map(
            {
                key: {
                    "compare_key": key,
                    "market_label": "To Score A Run",
                    "market_family": "runs_player",
                    "source": "fanduel",
                    "source_label": "FanDuel",
                    "source_bookmaker": "FanDuel",
                    "outcomes": {
                        "Yes": {"american": -120, "decimal_raw": 1.83, "decimal_fr": 1.83},
                        "No": {"american": -110, "decimal_raw": 1.91, "decimal_fr": 1.91},
                    },
                }
            },
            rotowire_rows=[
                RotoWireRunsRow(
                    player_name="CJ Abrams",
                    home_team="Atlanta Braves",
                    away_team="Washington Nationals",
                    over_line=0.5,
                    over_american=110,
                    under_american=-150,
                )
            ],
            home_team="Atlanta Braves",
            away_team="Washington Nationals",
            roster=["CJ Abrams"],
            rotowire_captured_at="2026-07-30T08:00:00+00:00",
        )
        self.assertEqual(merged[key]["outcomes"]["Yes"]["us_source"], "rotowire")
        self.assertEqual(merged[key]["outcomes"]["No"]["us_source"], "fanduel")


if __name__ == "__main__":
    unittest.main()
