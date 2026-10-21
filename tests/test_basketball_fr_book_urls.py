"""URLs FR stockees sur chaque issue (repli si book_events incomplet)."""

from __future__ import annotations

import time
import unittest

from book_urls import attach_fr_book_urls, selection_id_for_normalized_outcome
from compare_wnba_props_vs_fanduel import build_best_fr_player_props_map
from basketball_books_mapping import normalize_winamax_market
from basketball_market_mapping import (
    build_double_double_key,
    build_player_prop_key,
    build_player_tier_prop_key,
)


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

    def test_unibet_performance_board_maps_quickly_with_selection_ids(self) -> None:
        """Un tableau Performance (centaines d'issues) doit mapper en bien moins d'une seconde."""
        players = [
            "Jayson Tatum",
            "Jaylen Brown",
            "Kristaps Porzingis",
            "Derrick White",
            "Jrue Holiday",
            "Al Horford",
            "Giannis Antetokounmpo",
            "Damian Lillard",
            "Khris Middleton",
            "Brook Lopez",
            "Bobby Portis",
            "Malik Beasley",
            "Pat Connaughton",
            "Taurean Prince",
            "Sam Hauser",
            "Payton Pritchard",
        ]
        outcomes: list[tuple[str, float]] = []
        for player in players:
            for threshold in range(5, 36):
                outcomes.append((f"{player} {threshold}+", 1.5))
            outcomes.append((f"{player} + de 24,5", 1.91))
            outcomes.append((f"{player} - de 24,5", 1.85))
        selection_ids = {label: f"sid-{index}" for index, (label, _odds) in enumerate(outcomes)}
        event = {
            "url": "https://www.unibet.fr/event",
            "event_id": "99",
            "markets": [
                {
                    "label": "Performance Joueur-Point(s) - Match",
                    "outcomes": outcomes,
                    "selection_ids": selection_ids,
                }
            ],
        }
        started = time.perf_counter()
        fr_map = build_best_fr_player_props_map({"unibet": event}, roster=players)
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 1.0, f"map FR trop lent: {elapsed:.2f}s")
        key = build_player_prop_key("points_player", "Jayson Tatum", "24.5", roster=players)
        self.assertIn(key, fr_map)
        over = fr_map[key]["outcomes"]["Over"]
        self.assertEqual(over["odds"], 1.91)
        tatum_over = next(label for label, _odds in outcomes if label == "Jayson Tatum + de 24,5")
        self.assertEqual(over["selection_id"], selection_ids[tatum_over])
        tier_key = build_player_tier_prop_key("points_player", "Jayson Tatum", 25, roster=players)
        self.assertIn(tier_key, fr_map)
        tier = fr_map[tier_key]["outcomes"]["Over"]
        tatum_tier = next(label for label, _odds in outcomes if label == "Jayson Tatum 25+")
        self.assertEqual(tier["selection_id"], selection_ids[tatum_tier])
        self.assertGreater(len(fr_map), 100)

    def test_double_double_yes_keeps_selection_id(self) -> None:
        event = {
            "url": "https://www.winamax.fr/paris-sportifs/match/7",
            "match_id": "7",
            "markets": [
                {
                    "label": "Double-double",
                    "outcomes": [("Jayson Tatum", 1.7), ("Jaylen Brown", 2.1)],
                    "selection_ids": {
                        "Jayson Tatum": "dd-1",
                        "Jaylen Brown": "dd-2",
                    },
                }
            ],
        }
        fr_map = build_best_fr_player_props_map(
            {"winamax": event},
            roster=["Jayson Tatum", "Jaylen Brown"],
        )
        key = build_double_double_key("Jayson Tatum", roster=["Jayson Tatum", "Jaylen Brown"])
        self.assertIn(key, fr_map)
        self.assertEqual(fr_map[key]["outcomes"]["Yes"]["selection_id"], "dd-1")

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
