"""URLs FR stockees sur chaque issue (repli si book_events incomplet)."""

from __future__ import annotations

import unittest

from book_urls import attach_fr_book_urls, selection_id_for_normalized_outcome
from compare_wnba_props_vs_fanduel import build_best_fr_player_props_map
from basketball_books_mapping import normalize_winamax_market


class BasketballFrBookUrlTests(unittest.TestCase):
    def test_build_best_fr_stores_book_url_and_match_id(self) -> None:
        event = {
            "url": "https://www.winamax.fr/paris-sportifs/match/123",
            "match_id": "123",
            "markets": [
                {
                    "label": "Nombre de points du joueur - Test Player (10.5)",
                    "outcomes": [("Plus de 10,5", 1.9), ("Moins de 10,5", 1.85)],
                    "selection_ids": {
                        "Plus de 10,5": "9:8",
                        "Moins de 10,5": "9:7",
                    },
                }
            ],
        }
        fr_map = build_best_fr_player_props_map(
            {"winamax": event},
            roster=["Test Player"],
        )
        key = next(iter(fr_map))
        payload = fr_map[key]["outcomes"]["Over"]
        self.assertEqual(payload["fr_book_url"], event["url"])
        self.assertEqual(payload["fr_book_match_id"], "123")
        self.assertEqual(payload["selection_id"], "9:8")

    def test_unibet_ou_selection_id_not_stolen_by_tier_on_same_market(self) -> None:
        sid = selection_id_for_normalized_outcome(
            normalized_outcome="Over",
            raw_outcomes=[
                ("Plus de 2,5", 1.7),
                ("Moins de 2,5", 1.9),
                ("Test Player 3+", 1.5),
            ],
            selection_ids={
                "Plus de 2,5": "sid-ou-over",
                "Moins de 2,5": "sid-ou-under",
                "Test Player 3+": "sid-tier",
            },
            player_name="Test Player",
            line="2.5",
        )
        self.assertEqual(sid, "sid-ou-over")

    def test_winamax_normalize_plus_moins(self) -> None:
        markets = normalize_winamax_market(
            "Nombre de rebonds du joueur - Test Player (2.5)",
            [("Plus de 2,5", 1.72), ("Moins de 2,5", 1.72)],
            ["Test Player"],
        )
        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0].compare_key.split("|")[-1], "2.5")


if __name__ == "__main__":
    unittest.main()
