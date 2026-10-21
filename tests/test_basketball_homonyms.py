"""Disambiguation joueurs WNBA/NBA (homonymes de nom de famille)."""

from __future__ import annotations

import time
import unittest

from basketball_books_mapping import match_player_name, normalize_winamax_market
from basketball_market_mapping import (
    basketball_players_match,
    build_player_prop_key,
    build_player_tier_prop_key,
    fanduel_market_names_other_player,
    player_compare_token,
    player_token,
    resolve_fanduel_match_for_fr_prop,
    resolve_roster_player,
)
from compare_wnba_props_vs_fanduel import compare_normalized_props


class BasketballHomonymTests(unittest.TestCase):
    def test_shared_last_name_gets_distinct_tokens(self) -> None:
        roster = ["A'ja Wilson", "Erica Wilson", "Caitlin Clark"]
        self.assertEqual(player_token("A'ja Wilson"), "wilson")
        self.assertEqual(player_token("Erica Wilson"), "wilson")
        self.assertEqual(player_compare_token("A'ja Wilson", roster), "ajawilson")
        self.assertEqual(player_compare_token("Erica Wilson", roster), "ericawilson")
        self.assertEqual(player_compare_token("Caitlin Clark", roster), "caitlinclark")
        # La clé ne change pas si l'homonyme est absent du roster.
        self.assertEqual(player_compare_token("A'ja Wilson"), "ajawilson")
        self.assertEqual(player_compare_token("Caitlin Clark"), "caitlinclark")

    def test_prop_keys_do_not_collide(self) -> None:
        roster = ["A'ja Wilson", "Erica Wilson"]
        aja = build_player_prop_key("points_player", "A'ja Wilson", 22.5, roster=roster)
        erica = build_player_prop_key("points_player", "Erica Wilson", 8.5, roster=roster)
        self.assertEqual(aja, "points_player|ajawilson|22.5")
        self.assertEqual(erica, "points_player|ericawilson|8.5")
        self.assertNotEqual(aja.split("|")[1], erica.split("|")[1])

    def test_resolve_does_not_pick_first_homonym(self) -> None:
        roster = ["A'ja Wilson", "Erica Wilson"]
        # Label last-name only → ambiguous, keep raw label (no silent wrong match).
        self.assertEqual(resolve_roster_player("Wilson", roster), "Wilson")
        self.assertEqual(resolve_roster_player("A. Wilson", roster), "A'ja Wilson")
        self.assertEqual(resolve_roster_player("Erica Wilson", roster), "Erica Wilson")
        self.assertEqual(match_player_name("A'ja Wilson", roster), "A'ja Wilson")

    def test_full_name_token_does_not_shrink(self) -> None:
        roster = ["Caitlin Clark", "A'ja Wilson"]
        self.assertEqual(
            build_player_prop_key("points_player", "Caitlin Clark", 20.5, roster=roster),
            "points_player|caitlinclark|20.5",
        )

    def test_same_first_initial_and_last_name_distinct_tokens(self) -> None:
        roster = ["Jrue Holiday", "Justin Holiday", "Anthony Davis"]
        self.assertEqual(player_compare_token("Jrue Holiday", roster), "jrueholiday")
        self.assertEqual(player_compare_token("Justin Holiday", roster), "justinholiday")
        self.assertEqual(player_compare_token("Jrue Holiday"), "jrueholiday")
        jrue = build_player_prop_key("assists_player", "Jrue Holiday", 8.5, roster=roster)
        justin = build_player_prop_key("assists_player", "Justin Holiday", 4.5, roster=roster)
        self.assertNotEqual(jrue.split("|")[1], justin.split("|")[1])

    def test_jr_suffix_does_not_merge_different_players(self) -> None:
        """Derrick Jones Jr. ne prend pas la ligne 4,5 passes de Darius Acuff Jr."""
        derrick = player_compare_token("Derrick Jones Jr")
        darius = player_compare_token("Darius Acuff Jr.")
        self.assertEqual(derrick, "derrickjonesjr")
        self.assertEqual(darius, "dariusacuffjr")
        self.assertEqual(derrick, player_compare_token("Derrick Jones Jr.", ["Derrick Jones Jr."]))
        self.assertNotEqual(derrick, player_compare_token("Herbert Jones"))
        self.assertFalse(basketball_players_match("Derrick Jones Jr.", "Darius Acuff Jr."))
        tier_key = build_player_tier_prop_key("assists_player", "Derrick Jones Jr", 5)
        acuff_line = build_player_prop_key("assists_player", "Darius Acuff Jr.", "4.5")
        fd_map = {
            acuff_line: {
                "market_label": "Darius Acuff Jr. - Assists",
                "outcomes": {
                    "Over": {"decimal_fr": 1.72, "american": -138},
                    "Under": {"decimal_fr": 2.04, "american": 104},
                },
            }
        }
        self.assertIsNone(resolve_fanduel_match_for_fr_prop(tier_key, "Over", fd_map))
        own_line = build_player_prop_key("assists_player", "Derrick Jones Jr.", "4.5")
        self.assertEqual(tier_key.split("|")[1], own_line.split("|")[1])
        own_fd = {
            own_line: {
                "market_label": "Derrick Jones Jr. - Assists",
                "outcomes": {"Over": {"decimal_fr": 12.5, "american": 1100}},
            }
        }
        self.assertIsNotNone(resolve_fanduel_match_for_fr_prop(tier_key, "Over", own_fd))

    def test_same_last_name_and_father_son_stay_apart(self) -> None:
        self.assertEqual(player_compare_token("Herbert Jones"), "herbertjones")
        self.assertEqual(player_compare_token("Tre Jones"), "trejones")
        self.assertEqual(player_compare_token("Gary Trent"), "garytrent")
        self.assertEqual(player_compare_token("Gary Trent Jr."), "garytrentjr")
        self.assertFalse(basketball_players_match("Herbert Jones", "Tre Jones"))
        self.assertFalse(basketball_players_match("Jones", "Herbert Jones"))
        self.assertFalse(basketball_players_match("Gary Trent", "Gary Trent Jr"))
        self.assertFalse(basketball_players_match("Gary Trent Jr", "Gary Trent Sr"))
        # Le roster ne réécrit pas un nom complet, même s'il n'y a qu'un homonyme.
        self.assertEqual(player_compare_token("Gary Trent", ["Gary Trent Jr."]), "garytrent")
        self.assertEqual(player_compare_token("Gary Trent Jr", ["Gary Trent"]), "garytrentjr")
        self.assertEqual(player_compare_token("Herbert Jones", ["Tre Jones"]), "herbertjones")

    def test_initial_expands_only_when_unique(self) -> None:
        self.assertEqual(
            player_compare_token("A. Wilson", ["A'ja Wilson", "Caitlin Clark"]),
            "ajawilson",
        )
        self.assertEqual(
            player_compare_token("J. Holiday", ["Jrue Holiday", "Justin Holiday"]),
            "jholiday",
        )
        self.assertEqual(player_compare_token("J. Holiday", ["Jrue Holiday"]), "jrueholiday")
        self.assertEqual(resolve_roster_player("J. Holiday", ["Jrue Holiday", "Justin Holiday"]), "J. Holiday")

    def test_punctuation_does_not_split_one_player(self) -> None:
        self.assertEqual(player_compare_token("P.J. Washington"), "pjwashington")
        self.assertEqual(player_compare_token("PJ Washington"), "pjwashington")
        self.assertTrue(basketball_players_match("P.J. Washington", "PJ Washington"))
        self.assertEqual(player_compare_token("Karl-Anthony Towns"), "karlanthonytowns")
        self.assertEqual(player_compare_token("Karl Anthony Towns"), "karlanthonytowns")
        self.assertTrue(basketball_players_match("Nikola Jokić", "Nikola Jokic"))

    def test_fd_label_of_another_player_is_not_a_value(self) -> None:
        self.assertTrue(
            fanduel_market_names_other_player("Darius Acuff Jr. - Assists", "Derrick Jones Jr")
        )
        self.assertFalse(
            fanduel_market_names_other_player("Derrick Jones Jr. - Assists", "Derrick Jones Jr")
        )
        self.assertFalse(fanduel_market_names_other_player("To Record 6+ Assists", "Derrick Jones Jr"))
        # Même si la clé a été forcée (ancien bug « jr »), le libellé bloque la value.
        fr_key = "assists_player|jr|+5"
        fr_map = {
            fr_key: {
                "market_family": "assists_player",
                "player_name": "Derrick Jones Jr",
                "market_label_raw": "Nbre de passes decisives - Joueur - Match",
                "outcomes": {
                    "Over": {
                        "odds": 12.5,
                        "bookmaker_label": "Unibet",
                        "by_book": {},
                    }
                },
            }
        }
        fd_map = {
            "assists_player|jr|4.5": {
                "market_label": "Darius Acuff Jr. - Assists",
                "outcomes": {
                    "Over": {"decimal_fr": 1.72, "decimal_raw": 1.72, "american": -138},
                    "Under": {"decimal_fr": 2.04, "decimal_raw": 2.04, "american": 104},
                },
            }
        }
        self.assertEqual(compare_normalized_props(fr_map, fd_map), [])

    def test_same_first_name_different_last_names_do_not_fuzzy_match(self) -> None:
        self.assertFalse(basketball_players_match("Chris Paul", "Chris Banchero"))
        roster = ["Chris Paul", "Chris Banchero"]
        self.assertEqual(resolve_roster_player("Chris", roster), "Chris")

    def test_accent_and_spacing_duplicates_finish(self) -> None:
        """Jokic/Jokić et « J. Holiday » / « J Holiday » ne doivent pas boucler."""
        roster = [
            "Nikola Jokic",
            "Nikola Jokić",
            "J. Holiday",
            "J Holiday",
            "Jamal Murray",
        ]
        started = time.perf_counter()
        jokic = player_compare_token("Nikola Jokić", roster)
        holiday = player_compare_token("J Holiday", roster)
        murray = player_compare_token("Jamal Murray", roster)
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 0.5)
        self.assertEqual(jokic, player_compare_token("Nikola Jokic", roster))
        self.assertEqual(holiday, player_compare_token("J. Holiday", roster))
        self.assertEqual(murray, "jamalmurray")
        self.assertNotEqual(jokic, murray)

    def test_winamax_fr_and_key_align_with_roster(self) -> None:
        roster = ["A'ja Wilson", "Erica Wilson"]
        markets = normalize_winamax_market(
            "Nombre de points du joueur - A'ja Wilson (22.5)",
            [("Plus de 22,5", 1.85), ("Moins de 22,5", 1.90)],
            roster,
        )
        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0].compare_key, "points_player|ajawilson|22.5")
        self.assertEqual(markets[0].player_name, "A'ja Wilson")


if __name__ == "__main__":
    unittest.main()
