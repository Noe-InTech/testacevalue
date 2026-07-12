import unittest

from compare_tennis_aces_vs_fanduel import compare_normalized_aces


class SetAcesCompareTests(unittest.TestCase):
    def test_set_total_tier_matches_betclic_tier(self) -> None:
        fr_map = {
            "aces_set_total|3|6.5": {
                "compare_key": "aces_set_total|3|6.5",
                "market_family": "aces_set_total",
                "market_label_raw": "3eme set - Nombre total d'aces",
                "outcomes": {
                    "Over": {
                        "odds": 1.57,
                        "bookmaker": "betclic",
                        "bookmaker_label": "Betclic",
                    }
                },
            }
        }
        fd_map = {
            "aces_set_total|3|6.5": {
                "compare_key": "aces_set_total|3|6.5",
                "market_label": "Set 3 Aces",
                "outcomes": {
                    "Over": {
                        "decimal_fr": 1.52,
                        "decimal_raw": 1.52,
                        "american": -192,
                        "fd_tier_runner": "7+",
                    }
                },
                "fd_line_source": "tier",
            }
        }
        rows = compare_normalized_aces(fr_map, fd_map)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["best_fr_bookmaker"], "Betclic")


if __name__ == "__main__":
    unittest.main()
