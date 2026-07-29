import unittest

from baseball_books_mapping import (
    normalize_betclic_market,
    normalize_unibet_market,
    normalize_winamax_market,
)
from baseball_market_mapping import (
    build_h2h_key,
    build_hr_player_key,
    build_inning1_runs_total_key,
    build_run_line_key,
    build_runs_total_key,
    build_runs_team_key,
    map_fanduel_market_to_entries,
    resolve_team_side,
    teams_match,
)
from betclic_baseball_client import BetclicBaseballClient
from tennis_market_mapping import players_match


class BaseballMappingTests(unittest.TestCase):
    def test_team_side_abbreviations(self) -> None:
        self.assertEqual(
            resolve_team_side("MIA Marlins", "Miami Marlins", "Philadelphia Phillies"),
            "home",
        )
        self.assertEqual(
            resolve_team_side("PHI Phillies", "Miami Marlins", "Philadelphia Phillies"),
            "away",
        )
        self.assertEqual(
            resolve_team_side("Tie", "Miami Marlins", "Philadelphia Phillies"),
            "draw",
        )

    def test_teams_match_swapped(self) -> None:
        self.assertTrue(
            teams_match(
                "Miami Marlins",
                "Philadelphia Phillies",
                "Philadelphia Phillies",
                "Miami Marlins",
            )
        )

    def test_normalize_unibet_h2h(self) -> None:
        markets = normalize_unibet_market(
            "Face à Face - Match",
            [("MIA Marlins", 2.45), ("PHI Phillies", 1.54)],
            home_team="Miami Marlins",
            away_team="Philadelphia Phillies",
        )
        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0].compare_key, build_h2h_key())
        labels = {item.label for item in markets[0].outcomes}
        self.assertEqual(labels, {"home", "away"})

    def test_normalize_unibet_run_line(self) -> None:
        markets = normalize_unibet_market(
            "Face à Face Handicap Points - Match",
            [
                ("MIA Marlins [+1,5]", 1.75),
                ("PHI Phillies [-1,5]", 1.85),
                ("MIA Marlins [+2,5]", 1.5),
                ("PHI Phillies [-2,5]", 2.3),
            ],
            home_team="Miami Marlins",
            away_team="Philadelphia Phillies",
        )
        keys = {item.compare_key for item in markets}
        self.assertIn(build_run_line_key(1.5), keys)
        self.assertIn(build_run_line_key(2.5), keys)

    def test_normalize_unibet_totals(self) -> None:
        markets = normalize_unibet_market(
            "Plus / Moins Points - Match",
            [("Plus 7,5", 1.72), ("Moins 7,5", 1.85), ("Plus 8,5", 2.0), ("Moins 8,5", 1.6)],
            home_team="Miami Marlins",
            away_team="Philadelphia Phillies",
        )
        keys = {item.compare_key for item in markets}
        self.assertIn(build_runs_total_key(7.5), keys)
        self.assertIn(build_runs_total_key(8.5), keys)

    def test_normalize_unibet_f5(self) -> None:
        markets = normalize_unibet_market(
            "Vainqueur du Inning 1 au Inning 5 - Temps réglementaire",
            [("MIA Marlins", 2.1), ("PHI Phillies", 1.45)],
            home_team="Miami Marlins",
            away_team="Philadelphia Phillies",
        )
        self.assertEqual(markets[0].compare_key, "f5_h2h")

    def test_normalize_winamax_team_total(self) -> None:
        markets = normalize_winamax_market(
            "Nombre de runs de Miami Marlins (3.5)",
            [("Plus de 3,5", 1.85), ("Moins de 3,5", 1.85)],
            home_team="Miami Marlins",
            away_team="Philadelphia Phillies",
        )
        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0].compare_key, build_runs_team_key("Miami Marlins", 3.5))

    def test_normalize_winamax_hr_player(self) -> None:
        markets = normalize_winamax_market(
            "Marqueur de Home Run",
            [("Kyle Schwarber", 3.5), ("Bryce Harper", 4.2)],
            home_team="Miami Marlins",
            away_team="Philadelphia Phillies",
            roster=["Kyle Schwarber", "Bryce Harper"],
        )
        keys = {item.compare_key for item in markets}
        self.assertIn(build_hr_player_key("Kyle Schwarber"), keys)
        self.assertEqual(markets[0].outcomes[0].label, "Yes")

    def test_normalize_winamax_runs_player_tier(self) -> None:
        markets = normalize_winamax_market(
            "Marque 2 runs ou plus",
            [("Kyle Schwarber", 4.5)],
            home_team="Miami Marlins",
            away_team="Philadelphia Phillies",
            roster=["Kyle Schwarber"],
        )
        self.assertEqual(markets[0].compare_key, "runs_player|schwarber|2")

    def test_normalize_betclic_h2h(self) -> None:
        markets = normalize_betclic_market(
            "Vainqueur du match",
            [("Miami Marlins", 2.4), ("Philadelphia Phillies", 1.55)],
            home_team="Miami Marlins",
            away_team="Philadelphia Phillies",
        )
        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0].compare_key, build_h2h_key())
        self.assertEqual({o.label for o in markets[0].outcomes}, {"home", "away"})

    def test_normalize_betclic_run_line(self) -> None:
        markets = normalize_betclic_market(
            "Handicap",
            [
                ("Miami Marlins (+1.5)", 1.8),
                ("Philadelphia Phillies (-1.5)", 1.9),
            ],
            home_team="Miami Marlins",
            away_team="Philadelphia Phillies",
        )
        self.assertEqual(markets[0].compare_key, build_run_line_key(1.5))

    def test_normalize_betclic_runs_total(self) -> None:
        markets = normalize_betclic_market(
            "Nombre total de runs",
            [("Plus de 7,5", 1.9), ("Moins de 7,5", 1.8)],
            home_team="Miami Marlins",
            away_team="Philadelphia Phillies",
        )
        self.assertEqual(markets[0].compare_key, build_runs_total_key(7.5))

    def test_normalize_betclic_team_total(self) -> None:
        markets = normalize_betclic_market(
            "Nombre de runs de Miami Marlins (3.5)",
            [("Plus de 3,5", 1.85), ("Moins de 3,5", 1.85)],
            home_team="Miami Marlins",
            away_team="Philadelphia Phillies",
        )
        self.assertEqual(markets[0].compare_key, build_runs_team_key("Miami Marlins", 3.5))

    def test_betclic_slug_teams(self) -> None:
        home, away = BetclicBaseballClient._teams_from_slug(
            "miami-marlins-philadelphia-phillies-m12345"
        )
        self.assertEqual(home, "Miami Marlins")
        self.assertEqual(away, "Philadelphia Phillies")
        home2, away2 = BetclicBaseballClient._teams_from_slug(
            "lg-twins-vs-kiwoom-heroes-m99"
        )
        self.assertEqual(home2, "LG Twins")
        self.assertEqual(away2, "Kiwoom Heroes")

    def test_map_fanduel_moneyline(self) -> None:
        market = {
            "marketName": "Moneyline",
            "marketType": "MONEY_LINE",
            "runners": [
                {"runnerName": "Miami Marlins", "runnerStatus": "ACTIVE"},
                {"runnerName": "Philadelphia Phillies", "runnerStatus": "ACTIVE"},
            ],
        }
        entries = map_fanduel_market_to_entries(
            market,
            home_team="Miami Marlins",
            away_team="Philadelphia Phillies",
            roster=[],
        )
        outcomes = {outcome for _key, outcome, _label, _runner in entries}
        self.assertEqual(outcomes, {"home", "away"})

    def test_map_fanduel_run_line(self) -> None:
        market = {
            "marketName": "Run Line",
            "marketType": "MATCH_HANDICAP_(2-WAY)",
            "runners": [
                {"runnerName": "Philadelphia Phillies", "handicap": -1.5, "runnerStatus": "ACTIVE"},
                {"runnerName": "Miami Marlins", "handicap": 1.5, "runnerStatus": "ACTIVE"},
            ],
        }
        entries = map_fanduel_market_to_entries(
            market,
            home_team="Miami Marlins",
            away_team="Philadelphia Phillies",
            roster=[],
        )
        self.assertTrue(all(key == build_run_line_key(1.5) for key, *_ in entries))

    def test_map_fanduel_total_runs(self) -> None:
        market = {
            "marketName": "Total Runs",
            "marketType": "TOTAL_POINTS_(OVER/UNDER)",
            "runners": [
                {"runnerName": "Over", "handicap": 7.5, "runnerStatus": "ACTIVE"},
                {"runnerName": "Under", "handicap": 7.5, "runnerStatus": "ACTIVE"},
            ],
        }
        entries = map_fanduel_market_to_entries(
            market,
            home_team="Miami Marlins",
            away_team="Philadelphia Phillies",
            roster=[],
        )
        keys = {key for key, *_ in entries}
        self.assertEqual(keys, {build_runs_total_key(7.5)})

    def test_map_fanduel_hr(self) -> None:
        market = {
            "marketName": "To Hit A Home Run",
            "marketType": "TO_HIT_A_HOME_RUN",
            "runners": [
                {"runnerName": "Kyle Schwarber", "runnerStatus": "ACTIVE"},
            ],
        }
        entries = map_fanduel_market_to_entries(
            market,
            home_team="Miami Marlins",
            away_team="Philadelphia Phillies",
            roster=["Kyle Schwarber"],
        )
        self.assertEqual(entries[0][0], build_hr_player_key("Kyle Schwarber"))
        self.assertEqual(entries[0][1], "Yes")

    def test_parse_signed_line_skips_inning_ordinals(self) -> None:
        from baseball_market_mapping import parse_signed_line

        self.assertEqual(parse_signed_line("1st Inning 0.5 Runs"), 0.5)
        self.assertEqual(parse_signed_line("1er manche - Nombre de runs (0.5)"), 0.5)
        self.assertEqual(parse_signed_line("1ère manche - Nombre de runs (1.5)"), 1.5)
        self.assertEqual(parse_signed_line("MIA Marlins [+1,5]"), 1.5)
        self.assertEqual(parse_signed_line("Over 8.5"), 8.5)

    def test_map_fanduel_skips_parlay_f5_run_line(self) -> None:
        market = {
            "marketName": "First 5 Innings Run Line / Total Runs Parlay",
            "marketType": "1ST_HALF_RUN_LINE",
            "runners": [
                {
                    "runnerName": "Athletics",
                    "handicap": -1.5,
                    "runnerStatus": "ACTIVE",
                },
                {
                    "runnerName": "Boston Red Sox",
                    "handicap": 1.5,
                    "runnerStatus": "ACTIVE",
                },
            ],
        }
        entries = map_fanduel_market_to_entries(
            market,
            home_team="Athletics",
            away_team="Boston Red Sox",
            roster=[],
        )
        self.assertEqual(entries, [])

    def test_map_fanduel_inning1_runs_uses_half_line(self) -> None:
        market = {
            "marketName": "1st Inning 0.5 Runs",
            "marketType": "1ST_INNING_TOTAL_RUNS",
            "runners": [
                {"runnerName": "Over", "runnerStatus": "ACTIVE"},
                {"runnerName": "Under", "runnerStatus": "ACTIVE"},
            ],
        }
        entries = map_fanduel_market_to_entries(
            market,
            home_team="Athletics",
            away_team="Boston Red Sox",
            roster=[],
        )
        keys = {key for key, *_ in entries}
        self.assertEqual(keys, {build_inning1_runs_total_key(0.5)})
        self.assertEqual({outcome for _k, outcome, *_ in entries}, {"Over", "Under"})

    def test_normalize_winamax_inning1_runs_half_line(self) -> None:
        markets = normalize_winamax_market(
            "1er manche - Nombre de runs (0.5)",
            [("Plus de 0,5", 1.9), ("Moins de 0,5", 1.8)],
            home_team="Athletics",
            away_team="Boston Red Sox",
        )
        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0].compare_key, build_inning1_runs_total_key(0.5))

    def test_kbo_team_match(self) -> None:
        self.assertTrue(players_match("LG Twins", "LG Twins"))
        self.assertTrue(players_match("Kia Tigers", "KIA Tigers"))


class BaseballCompareHelpersTests(unittest.TestCase):
    def test_compare_h2h_odds_alignment(self) -> None:
        from compare_baseball_vs_fanduel import compare_normalized_markets

        fr_map = {
            "h2h": {
                "compare_key": "h2h",
                "market_family": "h2h",
                "market_label_raw": "Face à Face - Match",
                "player_name": "",
                "line": "",
                "outcomes": {
                    "home": {"odds": 2.45, "bookmaker_label": "Unibet"},
                    "away": {"odds": 1.54, "bookmaker_label": "Unibet"},
                },
            }
        }
        fd_map = {
            "h2h": {
                "compare_key": "h2h",
                "market_label": "Moneyline",
                "market_family": "h2h",
                "outcomes": {
                    "home": {"decimal_fr": 2.4, "american": 140},
                    "away": {"decimal_fr": 1.6, "american": -167},
                },
            }
        }
        rows = compare_normalized_markets(
            fr_map,
            fd_map,
            home_team="Miami Marlins",
            away_team="Philadelphia Phillies",
        )
        self.assertEqual(len(rows), 2)
        home_row = next(row for row in rows if row["outcome"] == "home")
        self.assertEqual(home_row["best_side"], "fr")
        self.assertEqual(home_row["cote_fr"], "2,45")
        self.assertEqual(home_row["cote_fr_fanduel"], "2,40")
        self.assertTrue(home_row["paire_fd_complete"])

    def test_compare_totals_over_under(self) -> None:
        from compare_baseball_vs_fanduel import compare_normalized_markets

        key = build_runs_total_key(7.5)
        fr_map = {
            key: {
                "compare_key": key,
                "market_family": "runs_total",
                "market_label_raw": "Nombre de runs",
                "player_name": "",
                "line": "7.5",
                "outcomes": {
                    "Over": {"odds": 1.9, "bookmaker_label": "Winamax"},
                    "Under": {"odds": 1.85, "bookmaker_label": "Winamax"},
                },
            }
        }
        fd_map = {
            key: {
                "compare_key": key,
                "market_label": "Total Runs",
                "market_family": "runs_total",
                "outcomes": {
                    "Over": {"decimal_fr": 1.83, "american": -120},
                    "Under": {"decimal_fr": 1.98, "american": -102},
                },
            }
        }
        rows = compare_normalized_markets(fr_map, fd_map)
        over = next(row for row in rows if row["outcome"] == "Over")
        self.assertEqual(over["best_side"], "fr")
        self.assertIn("7,5", over["ligne_props_fr"])


if __name__ == "__main__":
    unittest.main()
