import unittest

from compare_tennis_breaks import build_combined_payload, parse_tennis_markets
from compare_tennis_victoires import (
    compare_normalized_victoires,
    format_ligne_victoires_fr,
    is_victoire_market_label,
)


class CompareTennisVictoiresTests(unittest.TestCase):
    def test_parse_markets_default_all(self) -> None:
        self.assertEqual(parse_tennis_markets(""), frozenset({"aces", "breaks", "victoires"}))
        self.assertEqual(parse_tennis_markets("all"), frozenset({"aces", "breaks", "victoires"}))

    def test_parse_markets_subset(self) -> None:
        self.assertEqual(parse_tennis_markets("victoires"), frozenset({"victoires"}))
        self.assertEqual(parse_tennis_markets("aces,ml"), frozenset({"aces", "victoires"}))

    def test_is_victoire_label(self) -> None:
        self.assertTrue(is_victoire_market_label("Vainqueur du match"))
        self.assertTrue(is_victoire_market_label("Moneyline"))
        self.assertTrue(is_victoire_market_label("Face à Face - Match"))
        self.assertTrue(is_victoire_market_label("Face à Face - Live Match"))
        self.assertFalse(is_victoire_market_label("Nombre d'aces"))
        self.assertFalse(is_victoire_market_label("Face à Face - Live 2eme Jeu / 2ème Set"))
        self.assertFalse(is_victoire_market_label("Face à Face - Live 2ème Set"))
        self.assertFalse(is_victoire_market_label("Vainqueur des Jeux 3 et 4 - Live 2ème Set"))

    def test_format_ligne(self) -> None:
        self.assertEqual(
            format_ligne_victoires_fr({"outcome": "Jannik Sinner"}),
            "Victoire — Jannik Sinner",
        )

    def test_compare_h2h_ev(self) -> None:
        fr_map = {
            "h2h": {
                "compare_key": "h2h",
                "market_family": "h2h",
                "market_label_raw": "Vainqueur du match",
                "outcomes": {
                    "A Player": {
                        "odds": 2.1,
                        "bookmaker": "unibet",
                        "bookmaker_label": "Unibet",
                    },
                    "B Player": {
                        "odds": 1.8,
                        "bookmaker": "betclic",
                        "bookmaker_label": "Betclic",
                    },
                },
            }
        }
        fd_map = {
            "h2h": {
                "compare_key": "h2h",
                "market_label": "Moneyline",
                "outcomes": {
                    "A Player": {"decimal_fr": 1.9, "decimal_raw": 1.9, "american": -111},
                    "B Player": {"decimal_fr": 2.0, "decimal_raw": 2.0, "american": 100},
                },
            }
        }
        rows = compare_normalized_victoires(fr_map, fd_map)
        self.assertEqual(len(rows), 2)
        by_outcome = {row["outcome"]: row for row in rows}
        self.assertEqual(by_outcome["A Player"]["meilleur_cote"], "FR")
        self.assertTrue(by_outcome["A Player"]["paire_fd_complete"])
        self.assertIsNotNone(by_outcome["A Player"]["ev_percent_raw"])

    def test_align_abbreviated_fr_vs_full_fd_names(self) -> None:
        from compare_tennis_victoires import (
            build_fanduel_victoires_normalized_map,
            compare_normalized_victoires,
        )

        home, away = "A.Bondar", "A.Charaeva"
        fr_map = {
            "h2h": {
                "compare_key": "h2h",
                "market_family": "h2h",
                "market_label_raw": "Vainqueur du match",
                "outcomes": {
                    home: {"odds": 1.64, "bookmaker": "unibet", "bookmaker_label": "Unibet"},
                    away: {"odds": 2.25, "bookmaker": "unibet", "bookmaker_label": "Unibet"},
                },
            }
        }
        fd_event = {
            "home_player": "Anna Bondar",
            "away_player": "Alina Charaeva",
            "markets": [
                {
                    "marketName": "Moneyline",
                    "runners": [
                        {
                            "runnerName": "Anna Bondar",
                            "runnerStatus": "ACTIVE",
                            "winRunnerOdds": {
                                "americanDisplayOdds": {"americanOddsInt": -167},
                                "trueOdds": {"decimalOdds": {"decimalOdds": 1.6}},
                            },
                        },
                        {
                            "runnerName": "Alina Charaeva",
                            "runnerStatus": "ACTIVE",
                            "winRunnerOdds": {
                                "americanDisplayOdds": {"americanOddsInt": 136},
                                "trueOdds": {"decimalOdds": {"decimalOdds": 2.36}},
                            },
                        },
                    ],
                }
            ],
        }
        # Sans roster ancre: clés FD pleine longueur → 0 jointures.
        fd_raw = build_fanduel_victoires_normalized_map(fd_event)
        self.assertEqual(len(compare_normalized_victoires(fr_map, fd_raw)), 0)
        # Avec roster ancre: Anna Bondar → A.Bondar.
        fd_aligned = build_fanduel_victoires_normalized_map(fd_event, home=home, away=away)
        rows = compare_normalized_victoires(fr_map, fd_aligned)
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["outcome"] for row in rows}, {home, away})

    def test_combined_payload_includes_victoires(self) -> None:
        payload = build_combined_payload([], partial=False, anchors_total=0)
        self.assertIn("victoires", payload)
        self.assertEqual(payload["victoires"]["source"], "tennis_victoires_comparable")
        self.assertEqual(sorted(payload["markets"]), ["aces", "breaks", "victoires"])

    def test_combined_payload_markets_filter(self) -> None:
        payload = build_combined_payload(
            [],
            partial=False,
            anchors_total=0,
            markets=frozenset({"victoires"}),
        )
        self.assertEqual(payload["markets"], ["victoires"])
        self.assertEqual(payload["aces"]["comparable_count"], 0)
        self.assertEqual(payload["victoires"]["comparable_count"], 0)


if __name__ == "__main__":
    unittest.main()
