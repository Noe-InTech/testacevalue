"""Cohérence WNBA — books FR ↔ RotoWire · DraftKings (pts/reb/ast/3pts)."""

from __future__ import annotations

import unittest

from basketball_books_mapping import (
    normalize_betclic_market,
    normalize_unibet_market,
    normalize_winamax_market,
)
from basketball_market_mapping import build_player_prop_key
from compare_wnba_props_vs_fanduel import (
    build_rotowire_player_props_map,
    compare_normalized_props,
    overlay_us_reference_map,
)
from fanduel_client import american_to_decimal_fr
from rotowire_basketball_props_client import (
    RotoWireBasketballPropRow,
    RotoWireBasketballPropsClient,
)


ROSTER = ["Caitlin Clark", "Aliyah Boston", "Kelsey Mitchell"]
HOME = "Portland Fire"
AWAY = "Indiana Fever"

SAMPLE_HTML = """
<script>
const prop = "pts"
data: [
  {
    "name": "Caitlin Clark",
    "team": "IND",
    "opp": "@POR",
    "draftkings_pts": "20.5",
    "draftkings_ptsOver": "-120",
    "draftkings_ptsUnder": "-110"
  },
  {
    "name": "Kelsey Mitchell",
    "team": "IND",
    "opp": "@POR",
    "draftkings_pts": "23.5",
    "draftkings_ptsOver": "-109",
    "draftkings_ptsUnder": "-122"
  },
  {
    "name": "Paige Bueckers",
    "team": "DAL",
    "opp": "@WAS",
    "draftkings_pts": "19.5",
    "draftkings_ptsOver": "-127",
    "draftkings_ptsUnder": "-105"
  },
  {
    "name": "Incomplete Pair",
    "team": "IND",
    "opp": "@POR",
    "draftkings_pts": "10.5",
    "draftkings_ptsOver": "-110",
    "draftkings_ptsUnder": ""
  }
]
const prop = "reb"
data: [{
  "name": "Aliyah Boston",
  "team": "IND",
  "opp": "@POR",
  "draftkings_reb": "8.5",
  "draftkings_rebOver": "-115",
  "draftkings_rebUnder": "-115"
}]
const prop = "ast"
data: [{
  "name": "Caitlin Clark",
  "team": "IND",
  "opp": "@POR",
  "draftkings_ast": "9.5",
  "draftkings_astOver": "108",
  "draftkings_astUnder": "-147"
}]
const prop = "threes"
data: [{
  "name": "Caitlin Clark",
  "team": "IND",
  "opp": "@POR",
  "draftkings_threes": "3.5",
  "draftkings_threesOver": "131",
  "draftkings_threesUnder": "-174"
}]
</script>
"""


def _fr_slot(
    compare_key: str,
    *,
    over: float,
    under: float,
    player: str,
    book: str = "Winamax",
) -> dict:
    family = compare_key.split("|", 1)[0]
    return {
        "compare_key": compare_key,
        "market_family": family,
        "market_label_raw": f"{player} FR",
        "player_name": player,
        "outcomes": {
            "Over": {"odds": over, "bookmaker": "winamax", "bookmaker_label": book},
            "Under": {"odds": under, "bookmaker": "winamax", "bookmaker_label": book},
        },
    }


def _rw_row(
    name: str,
    family: str,
    line: float,
    *,
    over: int = -110,
    under: int = -110,
    home: str = HOME,
    away: str = AWAY,
    label: str = "Points",
) -> RotoWireBasketballPropRow:
    return RotoWireBasketballPropRow(
        player_name=name,
        home_team=home,
        away_team=away,
        market_family=family,
        market_label=label,
        line=line,
        over_american=over,
        under_american=under,
    )


class WnbaDraftKingsParseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = RotoWireBasketballPropsClient("wnba")
        self.rows = self.client.extract_draftkings_prop_rows_from_html(SAMPLE_HTML)

    def test_parses_all_four_families(self) -> None:
        families = {row.market_family for row in self.rows}
        self.assertEqual(
            families,
            {"points_player", "rebounds_player", "assists_player", "threes_made_player"},
        )

    def test_skips_incomplete_over_under_pair(self) -> None:
        names = {row.player_name for row in self.rows}
        self.assertNotIn("Incomplete Pair", names)

    def test_away_at_home_matchup(self) -> None:
        clark = next(
            row
            for row in self.rows
            if row.player_name == "Caitlin Clark" and row.market_family == "points_player"
        )
        self.assertEqual(clark.home_team, "Portland Fire")
        self.assertEqual(clark.away_team, "Indiana Fever")
        self.assertEqual(clark.line, 20.5)
        self.assertEqual(clark.bookmaker, "DraftKings")

    def test_home_vs_away_without_at(self) -> None:
        client = RotoWireBasketballPropsClient("wnba")
        html = """
        const prop = "pts"
        data: [{
          "name": "Angel Reese",
          "team": "ATL",
          "opp": "SEA",
          "draftkings_pts": "12.5",
          "draftkings_ptsOver": "-105",
          "draftkings_ptsUnder": "-125"
        }]
        """
        rows = client.extract_draftkings_prop_rows_from_html(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].home_team, "Atlanta Dream")
        self.assertEqual(rows[0].away_team, "Seattle Storm")

    def test_unknown_team_abbr_dropped(self) -> None:
        client = RotoWireBasketballPropsClient("wnba")
        html = """
        const prop = "pts"
        data: [{
          "name": "Mystery Player",
          "team": "ZZZ",
          "opp": "@POR",
          "draftkings_pts": "10.5",
          "draftkings_ptsOver": "-110",
          "draftkings_ptsUnder": "-110"
        }]
        """
        self.assertEqual(client.extract_draftkings_prop_rows_from_html(html), [])


class WnbaFrDraftKingsKeyAlignmentTests(unittest.TestCase):
    def test_winamax_points_key_matches_rotowire(self) -> None:
        markets = normalize_winamax_market(
            "Nombre de points du joueur - Caitlin Clark (20.5)",
            [("Plus de 20,5", 1.85), ("Moins de 20,5", 1.9)],
            ROSTER,
        )
        self.assertEqual(markets[0].compare_key, "points_player|clark|20.5")
        rw = build_rotowire_player_props_map(
            [_rw_row("Caitlin Clark", "points_player", 20.5)],
            home_team=HOME,
            away_team=AWAY,
            roster=ROSTER,
        )
        self.assertIn(markets[0].compare_key, rw)

    def test_unibet_and_betclic_same_key_as_draftkings(self) -> None:
        unibet = normalize_unibet_market(
            "Plus / Moins Points - Caitlin Clark - Match",
            [("Plus 20.5", 1.8), ("Moins 20.5", 1.95)],
            ROSTER,
        )
        betclic = normalize_betclic_market(
            "Nombre de points du joueur (plus/moins)",
            [("Caitlin Clark + de 20,5", 1.82), ("Caitlin Clark - de 20,5", 1.92)],
            ROSTER,
        )
        expected = build_player_prop_key("points_player", "Caitlin Clark", 20.5)
        self.assertEqual(unibet[0].compare_key, expected)
        self.assertEqual(betclic[0].compare_key, expected)

    def test_rebounds_assists_threes_keys(self) -> None:
        reb = normalize_winamax_market(
            "Nombre de rebonds du joueur - Aliyah Boston (8.5)",
            [("Plus de 8,5", 1.7), ("Moins de 8,5", 2.05)],
            ROSTER,
        )
        ast = normalize_winamax_market(
            "Nombre de passes décisives du joueur - Caitlin Clark (9.5)",
            [("Plus de 9,5", 2.1), ("Moins de 9,5", 1.7)],
            ROSTER,
        )
        threes = normalize_winamax_market(
            "Nombre de paniers à 3 points du joueur - Caitlin Clark (3.5)",
            [("Plus de 3,5", 2.2), ("Moins de 3,5", 1.65)],
            ROSTER,
        )
        self.assertEqual(reb[0].compare_key, "rebounds_player|boston|8.5")
        self.assertEqual(ast[0].compare_key, "assists_player|clark|9.5")
        self.assertEqual(threes[0].compare_key, "threes_made_player|clark|3.5")


class WnbaDraftKingsIsolationTests(unittest.TestCase):
    def test_line_isolation(self) -> None:
        fr_map = {
            "points_player|clark|20.5": _fr_slot(
                "points_player|clark|20.5", over=1.9, under=1.85, player="Caitlin Clark"
            )
        }
        us_map = build_rotowire_player_props_map(
            [_rw_row("Caitlin Clark", "points_player", 19.5)],
            home_team=HOME,
            away_team=AWAY,
            roster=ROSTER,
        )
        self.assertEqual(compare_normalized_props(fr_map, us_map), [])

    def test_player_isolation(self) -> None:
        fr_map = {
            "points_player|clark|20.5": _fr_slot(
                "points_player|clark|20.5", over=1.9, under=1.85, player="Caitlin Clark"
            )
        }
        us_map = build_rotowire_player_props_map(
            [_rw_row("Kelsey Mitchell", "points_player", 20.5)],
            home_team=HOME,
            away_team=AWAY,
            roster=ROSTER,
        )
        self.assertEqual(compare_normalized_props(fr_map, us_map), [])

    def test_family_isolation(self) -> None:
        fr_map = {
            "points_player|clark|9.5": _fr_slot(
                "points_player|clark|9.5", over=1.9, under=1.85, player="Caitlin Clark"
            )
        }
        us_map = build_rotowire_player_props_map(
            [_rw_row("Caitlin Clark", "assists_player", 9.5, label="Assists")],
            home_team=HOME,
            away_team=AWAY,
            roster=ROSTER,
        )
        self.assertEqual(compare_normalized_props(fr_map, us_map), [])

    def test_matchup_isolation(self) -> None:
        mapped = build_rotowire_player_props_map(
            [
                _rw_row(
                    "Paige Bueckers",
                    "points_player",
                    19.5,
                    home="Washington Mystics",
                    away="Dallas Wings",
                )
            ],
            home_team=HOME,
            away_team=AWAY,
            roster=["Paige Bueckers"],
        )
        self.assertEqual(mapped, {})


class WnbaDraftKingsOverlayCompareTests(unittest.TestCase):
    def test_compare_uses_rotowire_when_fanduel_incomplete(self) -> None:
        fr_map = {
            "points_player|clark|20.5": _fr_slot(
                "points_player|clark|20.5", over=1.95, under=1.8, player="Caitlin Clark"
            )
        }
        incomplete_fd = {
            "points_player|clark|20.5": {
                "compare_key": "points_player|clark|20.5",
                "market_label": "Caitlin Clark - Points",
                "market_family": "points_player",
                "source": "fanduel",
                "source_label": "FanDuel",
                "source_bookmaker": "FanDuel",
                "outcomes": {
                    "Over": {"decimal_fr": 1.91, "american": -110},
                },
            }
        }
        us_map = overlay_us_reference_map(
            incomplete_fd,
            rotowire_rows=[_rw_row("Caitlin Clark", "points_player", 20.5, over=-120, under=-110)],
            home_team=HOME,
            away_team=AWAY,
            roster=ROSTER,
            rotowire_captured_at="2026-07-31T12:00:00+00:00",
        )
        self.assertEqual(us_map["points_player|clark|20.5"]["source"], "rotowire")
        rows = compare_normalized_props(fr_map, us_map)
        self.assertEqual(len(rows), 2)
        over = next(row for row in rows if row["outcome"] == "Over")
        self.assertEqual(over["us_source"], "rotowire")
        self.assertEqual(over["us_bookmaker"], "DraftKings")
        self.assertEqual(over["us_source_label"], "RotoWire")
        self.assertAlmostEqual(float(over["best_fr_odds"]), 1.95)
        expected_us = american_to_decimal_fr(-120)
        self.assertAlmostEqual(float(over["fanduel_odds"]), float(expected_us))
        self.assertTrue(over["paire_fd_complete"])

    def test_keeps_fanduel_when_pair_complete(self) -> None:
        complete_fd = {
            "points_player|clark|20.5": {
                "compare_key": "points_player|clark|20.5",
                "market_label": "Caitlin Clark - Points",
                "source": "fanduel",
                "source_label": "FanDuel",
                "source_bookmaker": "FanDuel",
                "outcomes": {
                    "Over": {"decimal_fr": 1.87, "american": -115},
                    "Under": {"decimal_fr": 1.95, "american": -105},
                },
            }
        }
        merged = overlay_us_reference_map(
            complete_fd,
            rotowire_rows=[_rw_row("Caitlin Clark", "points_player", 20.5)],
            home_team=HOME,
            away_team=AWAY,
            roster=ROSTER,
        )
        self.assertEqual(merged["points_player|clark|20.5"]["source"], "fanduel")

    def test_rotowire_fills_missing_key_entirely(self) -> None:
        fr_map = {
            "assists_player|clark|9.5": _fr_slot(
                "assists_player|clark|9.5", over=2.05, under=1.75, player="Caitlin Clark"
            )
        }
        us_map = overlay_us_reference_map(
            {},
            rotowire_rows=[_rw_row("Caitlin Clark", "assists_player", 9.5, over=108, under=-147, label="Assists")],
            home_team=HOME,
            away_team=AWAY,
            roster=ROSTER,
        )
        rows = compare_normalized_props(fr_map, us_map)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["us_source"] == "rotowire" for row in rows))

    def test_sample_html_end_to_end_keys(self) -> None:
        client = RotoWireBasketballPropsClient("wnba")
        rows = client.extract_draftkings_prop_rows_from_html(SAMPLE_HTML)
        us_map = build_rotowire_player_props_map(
            rows,
            home_team=HOME,
            away_team=AWAY,
            roster=ROSTER,
        )
        expected = {
            "points_player|clark|20.5",
            "points_player|mitchell|23.5",
            "rebounds_player|boston|8.5",
            "assists_player|clark|9.5",
            "threes_made_player|clark|3.5",
        }
        self.assertEqual(set(us_map), expected)
        # Other matchup must not leak into Fever @ Fire map.
        self.assertNotIn("points_player|bueckers|19.5", us_map)


class NbaDraftKingsPrepTests(unittest.TestCase):
    def test_nba_client_uses_nba_url_and_team_map(self) -> None:
        client = RotoWireBasketballPropsClient("nba")
        self.assertIn("/nba/", client.props_url)
        self.assertEqual(client.team_abbr_map["BOS"], "Boston Celtics")

    def test_nba_empty_slate_is_safe(self) -> None:
        client = RotoWireBasketballPropsClient("nba")
        self.assertEqual(client.extract_draftkings_prop_rows_from_html("<html></html>"), [])

    def test_nba_sample_parse_ready(self) -> None:
        html = """
        const prop = "pts"
        data: [{
          "name": "Jayson Tatum",
          "team": "BOS",
          "opp": "@NY",
          "draftkings_pts": "27.5",
          "draftkings_ptsOver": "-110",
          "draftkings_ptsUnder": "-120"
        }]
        """
        client = RotoWireBasketballPropsClient("nba")
        rows = client.extract_draftkings_prop_rows_from_html(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].home_team, "New York Knicks")
        self.assertEqual(rows[0].away_team, "Boston Celtics")
        self.assertEqual(rows[0].market_family, "points_player")


class WnbaDraftKingsLiveSmokeTests(unittest.TestCase):
    """Smoke live optionnel — ignore si réseau / page hors saison."""

    def test_live_wnba_draftkings_has_consistent_keys(self) -> None:
        client = RotoWireBasketballPropsClient("wnba", timeout=25.0)
        try:
            rows, _fetched_at = client.fetch_draftkings_prop_rows()
        except Exception as exc:  # noqa: BLE001 — smoke réseau
            self.skipTest(f"RotoWire indisponible: {exc}")
        if not rows:
            self.skipTest("Slate WNBA vide")
        families = {row.market_family for row in rows}
        self.assertTrue(families & {"points_player", "rebounds_player", "assists_player", "threes_made_player"})
        for row in rows:
            key = build_player_prop_key(row.market_family, row.player_name, row.line)
            self.assertRegex(key, r"^[a-z_]+\|[a-z0-9]+\|\d+(?:\.\d+)?$")
            self.assertEqual(row.bookmaker, "DraftKings")
            self.assertTrue(row.home_team)
            self.assertTrue(row.away_team)


if __name__ == "__main__":
    unittest.main()
