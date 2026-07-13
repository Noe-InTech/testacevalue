import unittest

from compare_tennis_breaks import (
    compare_normalized_breaks,
    is_comparable_break_key,
)
from scan_tennis_aces import is_breaks_market


class BreaksAllMarketsTests(unittest.TestCase):
    def test_is_comparable_break_key(self) -> None:
        self.assertTrue(is_comparable_break_key("first_break"))
        self.assertTrue(is_comparable_break_key("breaks_total|5.5"))
        self.assertTrue(is_comparable_break_key("tie_break_set|1"))
        self.assertFalse(is_comparable_break_key("service_game_result|x|1|1"))

    def test_first_break_overlap(self) -> None:
        fr_map = {
            "first_break": {
                "compare_key": "first_break",
                "market_family": "first_break",
                "market_label_raw": "1er joueur à réussir un break - Match",
                "outcomes": {
                    "Jannik Sinner": {
                        "odds": 1.45,
                        "bookmaker": "unibet",
                        "bookmaker_label": "Unibet",
                    },
                    "Carlos Alcaraz": {
                        "odds": 2.7,
                        "bookmaker": "unibet",
                        "bookmaker_label": "Unibet",
                    },
                },
            }
        }
        fd_map = {
            "first_break": {
                "compare_key": "first_break",
                "market_label": "Service Break Number 1",
                "outcomes": {
                    "Jannik Sinner": {
                        "decimal_fr": 1.5,
                        "decimal_raw": 1.5,
                        "american": -200,
                    },
                    "Carlos Alcaraz": {
                        "decimal_fr": 2.5,
                        "decimal_raw": 2.5,
                        "american": 150,
                    },
                },
                "fd_line_source": "player",
            }
        }
        rows = compare_normalized_breaks(fr_map, fd_map)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["ligne_breaks_fr"], "Premier break — Jannik Sinner")

    def test_tie_break_set_overlap(self) -> None:
        fr_map = {
            "tie_break_set|1": {
                "compare_key": "tie_break_set|1",
                "market_family": "tie_break_set",
                "market_label_raw": "Tie-break - 1er Set",
                "outcomes": {
                    "Oui": {"odds": 1.9, "bookmaker": "betclic", "bookmaker_label": "Betclic"},
                    "Non": {"odds": 1.85, "bookmaker": "betclic", "bookmaker_label": "Betclic"},
                },
            }
        }
        fd_map = {
            "tie_break_set|1": {
                "compare_key": "tie_break_set|1",
                "market_label": "Set 1 Tie Break",
                "outcomes": {
                    "Oui": {"decimal_fr": 1.88, "decimal_raw": 1.88, "american": -114},
                    "Non": {"decimal_fr": 1.87, "decimal_raw": 1.87, "american": -115},
                },
                "fd_line_source": "yes_no",
            }
        }
        rows = compare_normalized_breaks(fr_map, fd_map)
        self.assertEqual(len(rows), 2)

    def test_yes_no_set_tiebreak_not_break_market(self) -> None:
        self.assertFalse(
            is_breaks_market("Y aura-t-il un Tie-break dans le set ? - 1er Set")
        )

    def test_match_level_tiebreak_yes_no_is_break_market(self) -> None:
        self.assertTrue(
            is_breaks_market("Y aura-t-il au moins un Tie-break - Match")
        )

    def test_tie_break_match_yes_no_overlap(self) -> None:
        fr_map = {
            "tie_break_match|0.5": {
                "compare_key": "tie_break_match|0.5",
                "market_family": "tie_break_match",
                "market_label_raw": "Y aura-t-il au moins un Tie-break - Match",
                "outcomes": {
                    "Over": {"odds": 1.55, "bookmaker": "unibet", "bookmaker_label": "Unibet"},
                    "Under": {"odds": 2.35, "bookmaker": "unibet", "bookmaker_label": "Unibet"},
                },
            }
        }
        fd_map = {
            "tie_break_match|0.5": {
                "compare_key": "tie_break_match|0.5",
                "market_label": "Total Tie Breaks 0.5",
                "outcomes": {
                    "Over": {"decimal_fr": 1.5, "decimal_raw": 1.5, "american": -200},
                    "Under": {"decimal_fr": 2.5, "decimal_raw": 2.5, "american": 150},
                },
                "fd_line_source": "ou",
            }
        }
        rows = compare_normalized_breaks(fr_map, fd_map)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["ligne_breaks_fr"], "Plus de 0,5 tie-break(s) — match")


if __name__ == "__main__":
    unittest.main()
