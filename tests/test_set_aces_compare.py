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
        self.assertEqual(rows, [])  # tiers FD exclus des comparables (prix N+ != O/U)

    def test_aces_7_5_does_not_match_fd_6_5(self) -> None:
        fr_map = {
            "aces_player|gonzalo_bueno|7.5": {
                "compare_key": "aces_player|gonzalo_bueno|7.5",
                "market_family": "aces_player",
                "market_label_raw": "Nombre d'aces Bueno",
                "outcomes": {
                    "Over": {
                        "odds": 2.4,
                        "bookmaker": "winamax",
                        "bookmaker_label": "Winamax",
                    },
                    "Under": {
                        "odds": 1.5,
                        "bookmaker": "winamax",
                        "bookmaker_label": "Winamax",
                    },
                },
            }
        }
        fd_map = {
            "aces_player|gonzalo_bueno|6.5": {
                "compare_key": "aces_player|gonzalo_bueno|6.5",
                "market_label": "Gonzalo Bueno Aces",
                "outcomes": {
                    "Over": {"decimal_fr": 1.9, "decimal_raw": 1.9, "american": -111},
                    "Under": {"decimal_fr": 1.85, "decimal_raw": 1.85, "american": -118},
                },
                "fd_line_source": "ou",
            }
        }
        rows = compare_normalized_aces(fr_map, fd_map)
        self.assertEqual(rows, [])

    def test_aces_different_player_same_line_does_not_match(self) -> None:
        fr_map = {
            "aces_player|bueno|6.5": {
                "compare_key": "aces_player|bueno|6.5",
                "market_family": "aces_player",
                "market_label_raw": "Aces Bueno",
                "outcomes": {
                    "Over": {
                        "odds": 1.9,
                        "bookmaker": "unibet",
                        "bookmaker_label": "Unibet",
                    }
                },
            }
        }
        fd_map = {
            "aces_player|faria|6.5": {
                "compare_key": "aces_player|faria|6.5",
                "market_label": "Jaime Faria Aces",
                "outcomes": {
                    "Over": {"decimal_fr": 1.85, "decimal_raw": 1.85, "american": -118},
                },
                "fd_line_source": "ou",
            }
        }
        rows = compare_normalized_aces(fr_map, fd_map)
        self.assertEqual(rows, [])

    def test_aces_total_vs_player_does_not_match(self) -> None:
        fr_map = {
            "aces_total|8.5": {
                "compare_key": "aces_total|8.5",
                "market_family": "aces_total",
                "market_label_raw": "Total aces",
                "outcomes": {
                    "Over": {
                        "odds": 2.0,
                        "bookmaker": "unibet",
                        "bookmaker_label": "Unibet",
                    }
                },
            }
        }
        fd_map = {
            "aces_player|bueno|8.5": {
                "compare_key": "aces_player|bueno|8.5",
                "market_label": "Bueno Aces",
                "outcomes": {
                    "Over": {"decimal_fr": 1.9, "decimal_raw": 1.9, "american": -111},
                },
                "fd_line_source": "ou",
            }
        }
        rows = compare_normalized_aces(fr_map, fd_map)
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
