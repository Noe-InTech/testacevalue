import unittest

from compare_tennis_aces_vs_fanduel import compute_paired_value_fields, format_ev_percent


def _fr_payload(odds: float) -> dict:
    return {"odds": odds, "bookmaker_label": "Betclic"}


def _fr_market(over: float, under: float) -> dict:
    return {
        "outcomes": {
            "Over": _fr_payload(over),
            "Under": _fr_payload(under),
        }
    }


def _fd_market(over_american: int, under_american: int) -> dict:
    return {
        "outcomes": {
            "Over": {"american": over_american, "decimal_fr": 1.91},
            "Under": {"american": under_american, "decimal_fr": 1.95},
        }
    }


class AcesValueTests(unittest.TestCase):
    def test_paired_value_complete(self) -> None:
        fields = compute_paired_value_fields(
            outcome="Over",
            fr_payload=_fr_payload(2.10),
            fr_market=_fr_market(2.10, 1.75),
            fd_market=_fd_market(-110, -110),
        )
        self.assertTrue(fields["paire_fd_complete"])
        self.assertEqual(fields["cote_us_fanduel_contraire"], "-110")
        self.assertEqual(fields["cote_fr_contraire"], "1,75")
        self.assertTrue(fields["prob_fair_fanduel"])
        self.assertIsNotNone(fields["ev_percent_raw"])

    def test_paired_value_missing_fd_opposite(self) -> None:
        fd_market = {
            "outcomes": {
                "Over": {"american": -110, "decimal_fr": 1.91},
            }
        }
        fields = compute_paired_value_fields(
            outcome="Over",
            fr_payload=_fr_payload(2.10),
            fr_market=_fr_market(2.10, 1.75),
            fd_market=fd_market,
        )
        self.assertFalse(fields["paire_fd_complete"])
        self.assertEqual(fields["ev_percent"], "")

    def test_format_ev_percent(self) -> None:
        self.assertEqual(format_ev_percent(0.052), "+5,2%")


if __name__ == "__main__":
    unittest.main()
