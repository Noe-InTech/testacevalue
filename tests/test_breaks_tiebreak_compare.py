import unittest

from compare_tennis_breaks import compare_normalized_breaks


class BreaksTiebreakCompareTests(unittest.TestCase):
    def test_tie_break_match_overlap(self) -> None:
        fr_map = {
            "tie_break_match|1.5": {
                "compare_key": "tie_break_match|1.5",
                "market_family": "tie_break_match",
                "market_label_raw": "Plus / Moins tie-break - Match",
                "outcomes": {
                    "Over": {
                        "odds": 2.1,
                        "bookmaker": "unibet",
                        "bookmaker_label": "Unibet",
                    },
                    "Under": {
                        "odds": 1.65,
                        "bookmaker": "unibet",
                        "bookmaker_label": "Unibet",
                    },
                },
            }
        }
        fd_map = {
            "tie_break_match|1.5": {
                "compare_key": "tie_break_match|1.5",
                "market_label": "Total Tie Breaks 1.5",
                "outcomes": {
                    "Over": {"decimal_fr": 2.0, "decimal_raw": 2.0, "american": 100},
                    "Under": {"decimal_fr": 1.7, "decimal_raw": 1.7, "american": -143},
                },
                "fd_line_source": "ou",
            }
        }
        rows = compare_normalized_breaks(fr_map, fd_map)
        self.assertEqual(len(rows), 2)
        outcomes = {row["outcome"] for row in rows}
        self.assertEqual(outcomes, {"Over", "Under"})

    def test_tie_break_0_5_does_not_match_fd_1_5(self) -> None:
        fr_map = {
            "tie_break_match|0.5": {
                "compare_key": "tie_break_match|0.5",
                "market_family": "tie_break_match",
                "market_label_raw": "Y aura-t-il au moins un Tie-break - Match",
                "outcomes": {
                    "Under": {
                        "odds": 1.3,
                        "bookmaker": "unibet",
                        "bookmaker_label": "Unibet",
                    },
                },
            }
        }
        fd_map = {
            "tie_break_match|1.5": {
                "compare_key": "tie_break_match|1.5",
                "market_label": "Total Tie Breaks 1.5",
                "outcomes": {
                    "Over": {"decimal_fr": 12.0, "decimal_raw": 12.0, "american": 1100},
                    "Under": {"decimal_fr": 1.02, "decimal_raw": 1.02, "american": -4500},
                },
                "fd_line_source": "ou",
            }
        }
        rows = compare_normalized_breaks(fr_map, fd_map)
        self.assertEqual(rows, [])

    def test_breaks_7_5_does_not_match_fd_6_5(self) -> None:
        fr_map = {
            "breaks_total|7.5": {
                "compare_key": "breaks_total|7.5",
                "market_family": "breaks_total",
                "market_label_raw": "Nombre de breaks",
                "outcomes": {
                    "Over": {
                        "odds": 2.2,
                        "bookmaker": "unibet",
                        "bookmaker_label": "Unibet",
                    },
                },
            }
        }
        fd_map = {
            "breaks_total|6.5": {
                "compare_key": "breaks_total|6.5",
                "market_label": "Total Breaks 6.5",
                "outcomes": {
                    "Over": {"decimal_fr": 1.8, "decimal_raw": 1.8, "american": -125},
                },
                "fd_line_source": "ou",
            }
        }
        rows = compare_normalized_breaks(fr_map, fd_map)
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
