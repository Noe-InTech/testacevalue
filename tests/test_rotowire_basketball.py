"""Tests RotoWire basketball props + overlay US."""

from __future__ import annotations

import unittest

from compare_wnba_props_vs_fanduel import (
    build_rotowire_player_props_map,
    overlay_us_reference_map,
)
from rotowire_basketball_props_client import (
    RotoWireBasketballPropRow,
    RotoWireBasketballPropsClient,
)


SAMPLE_HTML = """
<script>
const prop = "pts"
data: [{
  "name": "Caitlin Clark",
  "team": "IND",
  "opp": "@POR",
  "draftkings_pts": "18.5",
  "draftkings_ptsOver": "-110",
  "draftkings_ptsUnder": "-120"
}]
const prop = "reb"
data: [{
  "name": "Caitlin Clark",
  "team": "IND",
  "opp": "@POR",
  "draftkings_reb": "5.5",
  "draftkings_rebOver": "105",
  "draftkings_rebUnder": "-135"
}]
</script>
"""


class RotoWireBasketballTests(unittest.TestCase):
    def test_extract_wnba_draftkings_pts_reb(self) -> None:
        client = RotoWireBasketballPropsClient("wnba")
        rows = client.extract_draftkings_prop_rows_from_html(SAMPLE_HTML)
        self.assertEqual(len(rows), 2)
        pts = next(row for row in rows if row.market_family == "points_player")
        self.assertEqual(pts.player_name, "Caitlin Clark")
        self.assertEqual(pts.home_team, "Portland Fire")
        self.assertEqual(pts.away_team, "Indiana Fever")
        self.assertEqual(pts.line, 18.5)
        self.assertEqual(pts.over_american, -110)
        self.assertEqual(pts.under_american, -120)
        self.assertEqual(pts.bookmaker, "DraftKings")

    def test_nba_empty_html_returns_no_rows(self) -> None:
        client = RotoWireBasketballPropsClient("nba")
        rows = client.extract_draftkings_prop_rows_from_html("<html>no props</html>")
        self.assertEqual(rows, [])

    def test_overlay_prefers_complete_fanduel_pair(self) -> None:
        row = RotoWireBasketballPropRow(
            player_name="Caitlin Clark",
            home_team="Portland Fire",
            away_team="Indiana Fever",
            market_family="points_player",
            market_label="Points",
            line=18.5,
            over_american=-110,
            under_american=-120,
        )
        base = {
            "points_player|clark|18.5": {
                "compare_key": "points_player|clark|18.5",
                "source": "fanduel",
                "source_label": "FanDuel",
                "outcomes": {
                    "Over": {"decimal_fr": 1.91, "american": -110},
                    "Under": {"decimal_fr": 1.91, "american": -110},
                },
            }
        }
        merged = overlay_us_reference_map(
            base,
            rotowire_rows=[row],
            home_team="Portland Fire",
            away_team="Indiana Fever",
            roster=["Caitlin Clark"],
        )
        self.assertEqual(merged["points_player|clark|18.5"]["source"], "fanduel")

    def test_overlay_keeps_partial_fanduel(self) -> None:
        row = RotoWireBasketballPropRow(
            player_name="Caitlin Clark",
            home_team="Portland Fire",
            away_team="Indiana Fever",
            market_family="points_player",
            market_label="Points",
            line=18.5,
            over_american=-110,
            under_american=-120,
        )
        base = {
            "points_player|clark|18.5": {
                "compare_key": "points_player|clark|18.5",
                "source": "fanduel",
                "source_label": "FanDuel",
                "outcomes": {
                    "Over": {"decimal_fr": 1.91, "american": -110},
                },
            }
        }
        merged = overlay_us_reference_map(
            base,
            rotowire_rows=[row],
            home_team="Portland Fire",
            away_team="Indiana Fever",
            roster=["Caitlin Clark"],
        )
        market = merged["points_player|clark|18.5"]
        self.assertEqual(market["source"], "fanduel")
        self.assertNotIn("Under", market["outcomes"])

    def test_overlay_uses_rotowire_when_fanduel_missing(self) -> None:
        row = RotoWireBasketballPropRow(
            player_name="Caitlin Clark",
            home_team="Portland Fire",
            away_team="Indiana Fever",
            market_family="points_player",
            market_label="Points",
            line=18.5,
            over_american=-110,
            under_american=-120,
        )
        merged = overlay_us_reference_map(
            {},
            rotowire_rows=[row],
            home_team="Portland Fire",
            away_team="Indiana Fever",
            roster=["Caitlin Clark"],
        )
        market = merged["points_player|clark|18.5"]
        self.assertEqual(market["source"], "rotowire")
        self.assertEqual(market["source_bookmaker"], "DraftKings")
        self.assertIn("Under", market["outcomes"])

    def test_build_rotowire_map_keys(self) -> None:
        row = RotoWireBasketballPropRow(
            player_name="Angel Reese",
            home_team="Atlanta Dream",
            away_team="Seattle Storm",
            market_family="rebounds_player",
            market_label="Rebounds",
            line=11.5,
            over_american=-138,
            under_american=102,
        )
        mapped = build_rotowire_player_props_map(
            [row],
            home_team="Atlanta Dream",
            away_team="Seattle Storm",
            roster=["Angel Reese"],
        )
        self.assertIn("rebounds_player|reese|11.5", mapped)


if __name__ == "__main__":
    unittest.main()
