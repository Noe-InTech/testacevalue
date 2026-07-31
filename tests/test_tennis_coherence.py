"""Tests de cohérence tennis — identité joueurs, attribution cotes, familles/seuils."""

from __future__ import annotations

import unittest

from compare_tennis_aces_vs_fanduel import compare_normalized_aces
from compare_tennis_breaks import (
    build_best_fr_breaks_map,
    compare_normalized_breaks,
)
from compare_tennis_victoires import build_best_fr_victoires_map, compare_normalized_victoires
from tennis_books_mapping import (
    normalize_betclic_market,
    normalize_unibet_market,
    normalize_winamax_market,
    normalized_market_to_dict,
    player_key,
)
from tennis_market_mapping import (
    align_fr_outcome_to_fanduel,
    players_match,
    same_tennis_match,
    same_tennis_player,
)


HOME = "Jannik Sinner"
AWAY = "Novak Djokovic"


def _fr_ou(odds_over: float, odds_under: float, family: str, book: str = "Unibet") -> dict:
    return {
        "outcomes": {
            "Over": {"odds": odds_over, "bookmaker": "unibet", "bookmaker_label": book},
            "Under": {"odds": odds_under, "bookmaker": "unibet", "bookmaker_label": book},
        },
        "market_family": family,
        "market_label_raw": family,
    }


def _fd_ou(odds_over: float, odds_under: float, label: str = "Total") -> dict:
    return {
        "outcomes": {
            "Over": {"decimal_fr": odds_over, "decimal_raw": odds_over, "american": -110},
            "Under": {"decimal_fr": odds_under, "decimal_raw": odds_under, "american": -110},
        },
        "market_label": label,
        "fd_line_source": "ou",
    }


class TennisIdentityCoherenceTests(unittest.TestCase):
    def test_shared_firstname_not_same_player(self) -> None:
        self.assertFalse(same_tennis_player("Jiri Lehecka", "Jiri Vesely"))
        self.assertFalse(same_tennis_player("Daria Snigur", "Daria Egorova"))
        self.assertFalse(same_tennis_match("Daria Snigur", "X", "Daria Egorova", "Y"))

    def test_medvedev_medvedeva_prefix_trap(self) -> None:
        # players_match is fuzzy (prefix) — identity paths must stay strict.
        self.assertTrue(players_match("Daniil Medvedev", "Daria Medvedeva"))
        self.assertFalse(same_tennis_player("Daniil Medvedev", "Daria Medvedeva"))

    def test_shared_surname_keys_collide_today(self) -> None:
        """Documente le risque type Lowe: frères Zverev → même player_key."""
        self.assertEqual(player_key("Alexander Zverev"), player_key("Mischa Zverev"))
        self.assertTrue(same_tennis_player("Alexander Zverev", "Mischa Zverev"))

    def test_compound_and_initials_still_match(self) -> None:
        self.assertTrue(players_match("P.CarrenoBusta", "Pablo Carreno Busta"))
        self.assertTrue(same_tennis_player("J.Sinner", "Jannik Sinner"))
        self.assertTrue(same_tennis_match("J.Sinner", "N.Djokovic", HOME, AWAY))
        self.assertTrue(same_tennis_match(AWAY, HOME, HOME, AWAY))
        # Compound last-name keys still diverge (carreno vs busta) — fuzzy cover.
        self.assertFalse(same_tennis_player("P.CarrenoBusta", "Pablo Carreno Busta"))


class TennisAcesAttributionTests(unittest.TestCase):
    def test_unibet_aces_player_odds_stay_on_named_player(self) -> None:
        markets = normalize_unibet_market(
            "Plus / Moins 7,5 Aces - J.Sinner - Match",
            [("Plus", 1.72), ("Moins", 2.05)],
            HOME,
            AWAY,
        )
        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0].compare_key, "aces_player|sinner|7.5")
        self.assertEqual(markets[0].player_name, HOME)
        odds = {item.label: item.odds for item in markets[0].outcomes}
        self.assertEqual(odds["Over"], 1.72)
        self.assertEqual(odds["Under"], 2.05)

    def test_djokovic_aces_do_not_land_on_sinner_key(self) -> None:
        markets = normalize_unibet_market(
            "Plus / Moins 5,5 Aces - N.Djokovic - Match",
            [("Plus", 1.55), ("Moins", 2.35)],
            HOME,
            AWAY,
        )
        self.assertEqual(markets[0].compare_key, "aces_player|djokovic|5.5")
        self.assertNotEqual(markets[0].compare_key, "aces_player|sinner|5.5")

    def test_set_aces_isolated_from_match_aces(self) -> None:
        match_m = normalize_unibet_market(
            "Plus / Moins 3,5 Aces - J.Sinner - Match",
            [("Plus", 1.8), ("Moins", 1.9)],
            HOME,
            AWAY,
        )
        set_m = normalize_betclic_market(
            "1er set - Jannik Sinner - Nombre total d'aces",
            [("+ de 1,5", 1.7), ("+ de 2,5", 2.4)],
            HOME,
            AWAY,
        )
        match_keys = {item.compare_key for item in match_m}
        set_keys = {item.compare_key for item in set_m}
        self.assertTrue(any(k.startswith("aces_player|") for k in match_keys))
        self.assertTrue(any(k.startswith("aces_set_player|1|") for k in set_keys))
        self.assertTrue(match_keys.isdisjoint(set_keys))

    def test_player_line_isolation_in_compare(self) -> None:
        fr_map = {
            "aces_player|sinner|7.5": {
                **_fr_ou(1.72, 2.05, "aces_player"),
                "market_family": "aces_player",
            }
        }
        fd_map = {
            "aces_player|sinner|6.5": _fd_ou(1.7, 2.1, "Total Jannik Sinner Aces"),
            "aces_player|djokovic|7.5": _fd_ou(1.6, 2.2, "Total Novak Djokovic Aces"),
        }
        self.assertEqual(compare_normalized_aces(fr_map, fd_map), [])

    def test_winamax_and_unibet_same_aces_key(self) -> None:
        unibet = normalize_unibet_market(
            "Plus / Moins 4,5 Aces - J.Sinner - Match",
            [("Plus", 1.9), ("Moins", 1.85)],
            HOME,
            AWAY,
        )
        winamax = normalize_winamax_market(
            "Nombre d'aces de Jannik Sinner (4.5)",
            [("Plus", 1.88), ("Moins", 1.86)],
            HOME,
            AWAY,
        )
        self.assertEqual(unibet[0].compare_key, winamax[0].compare_key)


class TennisBreaksCoherenceTests(unittest.TestCase):
    def test_breaks_player_attribution(self) -> None:
        markets = normalize_unibet_market(
            "Plus / Moins 3,5 Break(s) - J.Sinner - Match",
            [("Plus", 2.1), ("Moins", 1.7)],
            HOME,
            AWAY,
        )
        self.assertEqual(markets[0].compare_key, "breaks_player|sinner|3.5")
        self.assertEqual(markets[0].player_name, HOME)

    def test_tiebreak_match_never_becomes_set1(self) -> None:
        markets = normalize_unibet_market(
            "Plus / Moins tie-break - Match",
            [("Plus 0,5", 1.4), ("Moins 0,5", 2.8)],
            HOME,
            AWAY,
        )
        keys = {item.compare_key for item in markets}
        self.assertIn("tie_break_match|0.5", keys)
        self.assertNotIn("tie_break_set|1", keys)

    def test_tiebreak_set2_numbering(self) -> None:
        markets = normalize_betclic_market(
            "Y aura-t-il un Tie-break dans le set ? - 2ème Set",
            [("Oui", 2.2), ("Non", 1.6)],
            HOME,
            AWAY,
        )
        self.assertTrue(any(item.compare_key == "tie_break_set|2" for item in markets))

    def test_first_break_fr_to_fd_join_through_pipeline(self) -> None:
        """Régression: canonical home/away ne doit pas casser le join vs noms FD."""
        book_events = {
            "unibet": {
                "home_player": HOME,
                "away_player": AWAY,
                "markets": [
                    {
                        "label": "1er joueur à réussir un break - Match",
                        "outcomes": [("J.Sinner", 1.45), ("N.Djokovic", 2.7)],
                    }
                ],
            }
        }
        fr_map = build_best_fr_breaks_map(book_events, home=HOME, away=AWAY)
        self.assertIn("first_break", fr_map)
        fr_outcomes = set(fr_map["first_break"]["outcomes"])
        self.assertEqual(fr_outcomes, {HOME, AWAY})

        fd_event = {
            "home_player": HOME,
            "away_player": AWAY,
            "markets": [
                {
                    "marketName": "Service Break Number 1",
                    "runners": [
                        {
                            "runnerName": HOME,
                            "runnerStatus": "ACTIVE",
                            "winRunnerOdds": [{"americanDisplayOdds": {"americanOdds": -200}}],
                        },
                        {
                            "runnerName": AWAY,
                            "runnerStatus": "ACTIVE",
                            "winRunnerOdds": [{"americanDisplayOdds": {"americanOdds": 150}}],
                        },
                    ],
                }
            ],
        }
        # Fallback if FanDuel price parsing shape differs: build map manually.
        fd_map = {
            "first_break": {
                "compare_key": "first_break",
                "market_label": "Service Break Number 1",
                "outcomes": {
                    HOME: {"decimal_fr": 1.5, "decimal_raw": 1.5, "american": -200},
                    AWAY: {"decimal_fr": 2.5, "decimal_raw": 2.5, "american": 150},
                },
                "fd_line_source": "player",
            }
        }
        rows = compare_normalized_breaks(fr_map, fd_map)
        self.assertEqual(len(rows), 2)
        by_outcome = {row["outcome"]: row for row in rows}
        self.assertAlmostEqual(float(by_outcome[HOME]["best_fr_odds"]), 1.45)
        self.assertAlmostEqual(float(by_outcome[AWAY]["best_fr_odds"]), 2.7)

    def test_align_home_away_tokens_for_first_break(self) -> None:
        self.assertEqual(
            align_fr_outcome_to_fanduel("home", "first_break", HOME, AWAY),
            HOME,
        )
        self.assertEqual(
            align_fr_outcome_to_fanduel("away", "first_break", HOME, AWAY),
            AWAY,
        )


class TennisVictoiresCoherenceTests(unittest.TestCase):
    def test_moneyline_sides_keep_odds(self) -> None:
        book_events = {
            "winamax": {
                "home_player": HOME,
                "away_player": AWAY,
                "markets": [
                    {
                        "label": "Vainqueur",
                        "outcomes": [(HOME, 1.35), (AWAY, 3.2)],
                    }
                ],
            }
        }
        fr_map = build_best_fr_victoires_map(book_events, home=HOME, away=AWAY)
        outcomes = fr_map["h2h"]["outcomes"]
        self.assertEqual(outcomes[HOME]["odds"], 1.35)
        self.assertEqual(outcomes[AWAY]["odds"], 3.2)

    def test_swapped_favorites_are_rejected(self) -> None:
        """Favori FR ≠ favori FD → pas de comparable (évite values inventées)."""
        fr_map = {
            "h2h": {
                "compare_key": "h2h",
                "market_family": "h2h",
                "market_label_raw": "Vainqueur",
                "outcomes": {
                    HOME: {"odds": 3.2, "bookmaker": "unibet", "bookmaker_label": "Unibet"},
                    AWAY: {"odds": 1.35, "bookmaker": "unibet", "bookmaker_label": "Unibet"},
                },
            }
        }
        fd_map = {
            "h2h": {
                "compare_key": "h2h",
                "market_label": "Moneyline",
                "outcomes": {
                    HOME: {"decimal_fr": 1.4, "decimal_raw": 1.4, "american": -250},
                    AWAY: {"decimal_fr": 3.0, "decimal_raw": 3.0, "american": 200},
                },
            }
        }
        self.assertEqual(compare_normalized_victoires(fr_map, fd_map), [])


class TennisDictCanonicalCoherenceTests(unittest.TestCase):
    def test_normalized_dict_home_away_roundtrip_aligns(self) -> None:
        markets = normalize_unibet_market(
            "1er joueur à réussir un break - Match",
            [("J.Sinner", 1.4), ("N.Djokovic", 2.8)],
            HOME,
            AWAY,
        )
        payload = normalized_market_to_dict(markets[0], HOME, AWAY)
        aligned = {
            align_fr_outcome_to_fanduel(outcome, "first_break", HOME, AWAY): odds
            for outcome, odds in payload["outcomes"].items()
        }
        self.assertEqual(set(aligned), {HOME, AWAY})
        self.assertEqual(aligned[HOME], 1.4)
        self.assertEqual(aligned[AWAY], 2.8)


if __name__ == "__main__":
    unittest.main()
