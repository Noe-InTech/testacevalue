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
        self.assertFalse(is_victoire_market_label("Nombre d'aces"))

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
