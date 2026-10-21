"""Pinnacle comme référence US optionnelle sur les props basket."""

from __future__ import annotations

import unittest

from compare_wnba_props_vs_fanduel import (
    build_pinnacle_player_props_map,
    overlay_us_reference_map,
)
from pinnacle_basketball_props_client import PinnacleBasketballPropsClient


def _matchup() -> dict:
    return {
        "id": 10,
        "isLive": False,
        "special": {
            "category": "Player Props",
            "description": "Jaren Jackson Jr. Total Points",
        },
        "parent": {
            "participants": [
                {"alignment": "home", "name": "Memphis Grizzlies"},
                {"alignment": "away", "name": "Utah Jazz"},
            ]
        },
        "participants": [
            {"id": 11, "name": "Over"},
            {"id": 12, "name": "Under"},
        ],
    }


def _market(**overrides) -> dict:
    market = {
        "matchupId": 10,
        "type": "total",
        "period": 0,
        "isAlternate": False,
        "prices": [
            {"participantId": 11, "points": 16.5, "price": -126},
            {"participantId": 12, "points": 16.5, "price": -105},
        ],
    }
    market.update(overrides)
    return market


class PinnacleBasketballPropTests(unittest.TestCase):
    def test_extracts_full_game_player_total(self) -> None:
        rows = PinnacleBasketballPropsClient.extract_prop_rows([_matchup()], [_market()])
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.player_name, "Jaren Jackson Jr.")
        self.assertEqual(row.market_family, "points_player")
        self.assertEqual(row.line, 16.5)
        self.assertEqual(row.over_american, -126)
        self.assertEqual(row.under_american, -105)
        self.assertEqual(row.home_team, "Memphis Grizzlies")
        self.assertEqual(row.away_team, "Utah Jazz")

    def test_skips_other_stats_live_and_alternate_lines(self) -> None:
        steals = _matchup()
        steals["id"] = 20
        steals["special"] = {"category": "Player Props", "description": "Jaren Jackson Jr. Total Steals"}
        live = _matchup()
        live["id"] = 30
        live["isLive"] = True
        rows = PinnacleBasketballPropsClient.extract_prop_rows(
            [_matchup(), steals, live],
            [
                _market(),
                _market(matchupId=30),
                _market(isAlternate=True),
            ],
        )
        self.assertEqual(len(rows), 1)
        self.assertFalse(any(row.player_name == "" for row in rows))

    def test_map_keeps_jr_in_the_compare_key(self) -> None:
        rows = PinnacleBasketballPropsClient.extract_prop_rows([_matchup()], [_market()])
        mapped = build_pinnacle_player_props_map(
            rows,
            home_team="Memphis Grizzlies",
            away_team="Utah Jazz",
            roster=["Jaren Jackson Jr."],
        )
        self.assertIn("points_player|jarenjacksonjr|16.5", mapped)

    def test_pinnacle_pair_replaces_fanduel_on_the_same_line(self) -> None:
        rows = PinnacleBasketballPropsClient.extract_prop_rows([_matchup()], [_market()])
        base = {
            "points_player|jarenjacksonjr|16.5": {
                "compare_key": "points_player|jarenjacksonjr|16.5",
                "source": "fanduel",
                "market_label": "Jaren Jackson Jr. - Points",
                "player_name": "Jaren Jackson Jr.",
                "outcomes": {
                    "Over": {"decimal_fr": 1.95, "american": -105},
                    "Under": {"decimal_fr": 1.95, "american": -105},
                },
            }
        }
        merged = overlay_us_reference_map(
            base,
            rotowire_rows=[],
            home_team="Memphis Grizzlies",
            away_team="Utah Jazz",
            roster=["Jaren Jackson Jr."],
            pinnacle_rows=rows,
        )
        market = merged["points_player|jarenjacksonjr|16.5"]
        self.assertEqual(market["source"], "pinnacle")
        self.assertEqual(market["outcomes"]["Over"]["us_source"], "pinnacle")
        self.assertEqual(market["outcomes"]["Over"]["american"], -126)
        self.assertEqual(market["player_name"], "Jaren Jackson Jr.")

    def test_fanduel_line_stays_when_pinnacle_has_no_match(self) -> None:
        rows = PinnacleBasketballPropsClient.extract_prop_rows([_matchup()], [_market()])
        base = {
            "points_player|jarenjacksonjr|22.5": {
                "compare_key": "points_player|jarenjacksonjr|22.5",
                "source": "fanduel",
                "outcomes": {
                    "Over": {"decimal_fr": 1.91, "american": -110},
                    "Under": {"decimal_fr": 1.91, "american": -110},
                },
            }
        }
        merged = overlay_us_reference_map(
            base,
            rotowire_rows=[],
            home_team="Memphis Grizzlies",
            away_team="Utah Jazz",
            roster=["Jaren Jackson Jr."],
            pinnacle_rows=rows,
        )
        self.assertEqual(merged["points_player|jarenjacksonjr|22.5"]["source"], "fanduel")
        self.assertEqual(merged["points_player|jarenjacksonjr|16.5"]["source"], "pinnacle")


if __name__ == "__main__":
    unittest.main()
