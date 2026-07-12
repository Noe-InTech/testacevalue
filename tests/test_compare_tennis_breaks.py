import unittest

from compare_tennis_breaks import build_combined_payload, format_ligne_breaks_fr
from scan_tennis_aces import is_breaks_market


class CompareTennisBreaksTests(unittest.TestCase):
    def test_format_ligne_breaks_fr(self) -> None:
        row = {
            "compare_key": "breaks_total|5.5",
            "outcome": "Over",
            "fr_market_label": "Nombre de breaks dans le match",
        }
        self.assertEqual(format_ligne_breaks_fr(row), "Plus de 5,5 breaks — match")

    def test_build_combined_payload_shape(self) -> None:
        results = [
            {
                "match": "A vs B",
                "comparables": [],
                "fr_only_aces": [],
                "fd_only_aces": [],
                "comparable_breaks": [],
                "fr_only_breaks": [],
                "fd_only_breaks": [],
                "fr_ace_market_count": 2,
                "fd_ace_market_count": 1,
                "fr_break_market_count": 1,
                "fd_break_market_count": 0,
            }
        ]
        payload = build_combined_payload(results, partial=False, anchors_total=1)
        self.assertIn("aces", payload)
        self.assertIn("breaks", payload)
        self.assertEqual(payload["source"], "tennis_props_comparable")
        self.assertEqual(payload["aces"]["comparable_count"], 0)
        self.assertEqual(payload["breaks"]["comparable_count"], 0)
        self.assertEqual(payload["matches_done"], 1)

    def test_yes_no_set_tiebreak_is_not_break_market(self) -> None:
        self.assertFalse(
            is_breaks_market("Y aura-t-il un Tie-break dans le set ? - 1er Set")
        )

    def test_ou_tiebreak_match_is_break_market(self) -> None:
        self.assertTrue(is_breaks_market("Plus / Moins tie-break - Match"))


if __name__ == "__main__":
    unittest.main()
