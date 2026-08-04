"""Disambiguation joueurs WNBA/NBA (homonymes de nom de famille)."""

from __future__ import annotations

import unittest

from basketball_books_mapping import match_player_name, normalize_winamax_market
from basketball_market_mapping import (
    build_player_prop_key,
    player_compare_token,
    player_token,
    resolve_roster_player,
)


class BasketballHomonymTests(unittest.TestCase):
    def test_shared_last_name_gets_distinct_tokens(self) -> None:
        roster = ["A'ja Wilson", "Erica Wilson", "Caitlin Clark"]
        self.assertEqual(player_token("A'ja Wilson"), "wilson")
        self.assertEqual(player_token("Erica Wilson"), "wilson")
        self.assertEqual(player_compare_token("A'ja Wilson", roster), "awilson")
        self.assertEqual(player_compare_token("Erica Wilson", roster), "ewilson")
        self.assertEqual(player_compare_token("Caitlin Clark", roster), "clark")

    def test_prop_keys_do_not_collide(self) -> None:
        roster = ["A'ja Wilson", "Erica Wilson"]
        aja = build_player_prop_key("points_player", "A'ja Wilson", 22.5, roster=roster)
        erica = build_player_prop_key("points_player", "Erica Wilson", 8.5, roster=roster)
        self.assertEqual(aja, "points_player|awilson|22.5")
        self.assertEqual(erica, "points_player|ewilson|8.5")
        self.assertNotEqual(aja.split("|")[1], erica.split("|")[1])

    def test_resolve_does_not_pick_first_homonym(self) -> None:
        roster = ["A'ja Wilson", "Erica Wilson"]
        # Label last-name only → ambiguous, keep raw label (no silent wrong match).
        self.assertEqual(resolve_roster_player("Wilson", roster), "Wilson")
        self.assertEqual(resolve_roster_player("A. Wilson", roster), "A'ja Wilson")
        self.assertEqual(resolve_roster_player("Erica Wilson", roster), "Erica Wilson")
        self.assertEqual(match_player_name("A'ja Wilson", roster), "A'ja Wilson")

    def test_unique_last_name_keeps_short_token(self) -> None:
        roster = ["Caitlin Clark", "A'ja Wilson"]
        self.assertEqual(
            build_player_prop_key("points_player", "Caitlin Clark", 20.5, roster=roster),
            "points_player|clark|20.5",
        )

    def test_winamax_fr_and_key_align_with_roster(self) -> None:
        roster = ["A'ja Wilson", "Erica Wilson"]
        markets = normalize_winamax_market(
            "Nombre de points du joueur - A'ja Wilson (22.5)",
            [("Plus de 22,5", 1.85), ("Moins de 22,5", 1.90)],
            roster,
        )
        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0].compare_key, "points_player|awilson|22.5")
        self.assertEqual(markets[0].player_name, "A'ja Wilson")


if __name__ == "__main__":
    unittest.main()
