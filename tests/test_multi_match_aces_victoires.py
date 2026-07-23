"""Tests multi-matchs aces (near-line, exclusion tier) + garde-fous victoires."""

from __future__ import annotations

import unittest

from compare_tennis_aces_vs_fanduel import (
    compare_normalized_aces,
    _find_fd_market_near_line,
)
from compare_tennis_victoires import (
    build_best_fr_victoires_map,
    compare_normalized_victoires,
    is_victoire_market_label,
)
from tennis_books_mapping import normalize_unibet_market


def _fr_ou(odds_over: float, odds_under: float, book: str = "Unibet") -> dict:
    return {
        "outcomes": {
            "Over": {"odds": odds_over, "bookmaker": "unibet", "bookmaker_label": book},
            "Under": {"odds": odds_under, "bookmaker": "unibet", "bookmaker_label": book},
        },
        "market_family": "aces_total",
        "market_label_raw": "Nombre d'aces",
    }


def _fd_ou(odds_over: float, odds_under: float, label: str = "Total Aces") -> dict:
    return {
        "outcomes": {
            "Over": {"decimal_fr": odds_over, "decimal_raw": odds_over, "american": -110},
            "Under": {"decimal_fr": odds_under, "decimal_raw": odds_under, "american": -110},
        },
        "market_label": label,
        "fd_line_source": "ou",
    }


def _fd_tier(odds_over: float, runner: str = "11+") -> dict:
    return {
        "outcomes": {
            "Over": {
                "decimal_fr": odds_over,
                "decimal_raw": odds_over,
                "american": -200,
                "fd_tier_runner": runner,
            }
        },
        "market_label": "Total Aces",
        "fd_line_source": "tier",
    }


class MultiMatchAcesVictoiresTests(unittest.TestCase):
    def test_near_line_matches_havlickova_style(self) -> None:
        """FR 3.5 vs FD 2.5 meme match total → comparable (delta 1.0)."""
        fr_map = {"aces_total|3.5": {**_fr_ou(1.9, 1.9), "market_family": "aces_total"}}
        fd_map = {"aces_total|2.5": _fd_ou(1.85, 1.95, "Total Aces 2.5")}
        key, market, delta = _find_fd_market_near_line("aces_total|3.5", fd_map)
        self.assertEqual(key, "aces_total|2.5")
        self.assertEqual(delta, 1.0)
        self.assertIsNotNone(market)
        rows = compare_normalized_aces(fr_map, fd_map)
        self.assertGreaterEqual(len(rows), 1)
        self.assertTrue(all(r.get("paire_fd_complete") for r in rows))

    def test_tier_never_enters_comparables(self) -> None:
        fr_map = {"aces_total|10.5": {**_fr_ou(1.42, 2.8), "market_family": "aces_total"}}
        fd_map = {"aces_total|10.5": _fd_tier(1.30, "11+")}
        rows = compare_normalized_aces(fr_map, fd_map)
        self.assertEqual(rows, [])

    def test_exact_ou_still_preferred(self) -> None:
        fr_map = {
            "aces_player|skatov|1.5": {
                **_fr_ou(1.80, 1.66, "Winamax"),
                "market_family": "aces_player",
            }
        }
        fd_map = {
            "aces_player|skatov|1.5": _fd_ou(2.30, 1.56, "Total Timofey Skatov Aces 1.5"),
            "aces_player|skatov|2.5": _fd_tier(4.0, "3+"),
        }
        rows = compare_normalized_aces(fr_map, fd_map)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r["fanduel_compare_key"] == "aces_player|skatov|1.5" for r in rows))

    def test_player_lines_do_not_cross_match(self) -> None:
        fr_map = {
            "aces_player|rublev|6.5": {
                **_fr_ou(1.86, 1.9),
                "market_family": "aces_player",
            }
        }
        fd_map = {
            "aces_player|skatov|6.5": _fd_ou(1.5, 2.4),
        }
        rows = compare_normalized_aces(fr_map, fd_map)
        self.assertEqual(rows, [])

    def test_batch_of_matches_aces(self) -> None:
        """Plusieurs matchs: seuls les O/U alignés (exact ou ±1) sortent."""
        cases = [
            (
                "aces_total|10.5",
                {"aces_total|10.5": _fd_ou(1.3, 3.2)},
                True,
            ),
            (
                "aces_total|10.5",
                {"aces_total|10.5": _fd_tier(1.3)},
                False,
            ),
            (
                "aces_total|3.5",
                {"aces_total|2.5": _fd_ou(1.8, 1.9)},
                True,
            ),
            (
                "aces_player|bublik|4.5",
                {"aces_player|bublik|5.5": _fd_ou(1.7, 2.0)},
                False,  # player: exact only, pas de near-line
            ),
        ]
        for fr_key, fd_map, expect in cases:
            fr_map = {fr_key: {**_fr_ou(1.7, 2.1), "market_family": fr_key.split("|")[0]}}
            rows = compare_normalized_aces(fr_map, fd_map)
            if expect:
                self.assertGreater(len(rows), 0, fr_key)
            else:
                self.assertEqual(rows, [], fr_key)

    def test_victoires_rejects_daria_firstname_collision(self) -> None:
        """Daria Snigur ne doit jamais alimenter Daria Egorova."""
        home, away = "Daria Egorova", "Ana Candiotto"
        book_events = {
            "betclic": {
                "home_player": "Lanlana Tararudee",
                "away_player": "Daria Snigur",
                "markets": [
                    {
                        "label": "Vainqueur du match",
                        "outcomes": [
                            ("Lanlana Tararudee", 2.18),
                            ("Daria Snigur", 1.56),
                        ],
                    }
                ],
            }
        }
        fr_map = build_best_fr_victoires_map(book_events, home=home, away=away)
        self.assertEqual(fr_map, {})

    def test_betclic_link_requires_both_surnames(self) -> None:
        from types import SimpleNamespace

        from compare_tennis_aces_vs_fanduel import find_betclic_link_for_players

        links = [
            SimpleNamespace(
                slug="lanlana-tararudee-daria-snigur-m1177350126440448",
                url="https://www.betclic.fr/x",
            ),
            SimpleNamespace(
                slug="daria-egorova-ana-candiotto-m1",
                url="https://www.betclic.fr/y",
            ),
        ]
        found = find_betclic_link_for_players(links, "Daria Egorova", "Ana Candiotto")
        self.assertIsNotNone(found)
        self.assertIn("egorova", found.slug)
        self.assertIsNone(
            find_betclic_link_for_players(
                links[:1], "Daria Egorova", "Ana Candiotto"
            )
        )

    def test_victoires_rejects_game_face_a_face_pollution(self) -> None:
        home, away = "A.Bublik", "A.Molcan"
        book_events = {
            "unibet": {
                "home_player": home,
                "away_player": away,
                "markets": [
                    {
                        "label": "Face à Face - Live Match",
                        "outcomes": [(home, 1.13), (away, 4.75)],
                    },
                    {
                        "label": "Face à Face - Live 2eme Jeu / 2ème Set",
                        "outcomes": [(home, 3.2), (away, 1.2)],
                    },
                ],
            }
        }
        fr_map = build_best_fr_victoires_map(book_events, home=home, away=away)
        outcomes = fr_map["h2h"]["outcomes"]
        self.assertAlmostEqual(outcomes[home]["odds"], 1.13, places=2)
        self.assertAlmostEqual(outcomes[away]["odds"], 4.75, places=2)

    def test_victoires_rejects_swapped_favorites(self) -> None:
        fr_map = {
            "h2h": {
                "market_label_raw": "Vainqueur",
                "outcomes": {
                    "A": {"odds": 3.2, "bookmaker_label": "Unibet"},
                    "B": {"odds": 1.3, "bookmaker_label": "Unibet"},
                },
            }
        }
        fd_map = {
            "h2h": {
                "market_label": "Moneyline",
                "outcomes": {
                    "A": {"decimal_fr": 1.15, "decimal_raw": 1.15, "american": -650},
                    "B": {"decimal_fr": 5.6, "decimal_raw": 5.6, "american": 460},
                },
            }
        }
        self.assertEqual(compare_normalized_victoires(fr_map, fd_map), [])

    def test_victoires_rejects_poison_favorite_price(self) -> None:
        """Meme favori mais FR 3.20 vs FD 1.15 → refuse (marche jeu)."""
        fr_map = {
            "h2h": {
                "market_label_raw": "Face à Face - Live Match",
                "outcomes": {
                    "A.Bublik": {"odds": 3.2, "bookmaker_label": "Unibet"},
                    "A.Molcan": {"odds": 4.9, "bookmaker_label": "Unibet"},
                },
            }
        }
        fd_map = {
            "h2h": {
                "market_label": "Moneyline",
                "outcomes": {
                    "A.Bublik": {"decimal_fr": 1.15, "decimal_raw": 1.15, "american": -650},
                    "A.Molcan": {"decimal_fr": 5.6, "decimal_raw": 5.6, "american": 460},
                },
            }
        }
        self.assertEqual(compare_normalized_victoires(fr_map, fd_map), [])

    def test_victoires_keeps_aligned_moneyline(self) -> None:
        fr_map = {
            "h2h": {
                "market_label_raw": "Face à Face - Live Match",
                "outcomes": {
                    "A.Bublik": {"odds": 1.13, "bookmaker_label": "Unibet"},
                    "A.Molcan": {"odds": 4.75, "bookmaker_label": "Unibet"},
                },
            }
        }
        fd_map = {
            "h2h": {
                "market_label": "Moneyline",
                "outcomes": {
                    "A.Bublik": {"decimal_fr": 1.15, "decimal_raw": 1.15, "american": -650},
                    "A.Molcan": {"decimal_fr": 5.6, "decimal_raw": 5.6, "american": 460},
                },
            }
        }
        rows = compare_normalized_victoires(fr_map, fd_map)
        self.assertEqual(len(rows), 2)
        by = {r["outcome"]: r for r in rows}
        self.assertEqual(by["A.Bublik"]["cote_fr"], "1,13")

    def test_normalize_unibet_batch_labels(self) -> None:
        home, away = "A.Bublik", "A.Molcan"
        accepted = []
        rejected = []
        for label, odds in [
            ("Face à Face - Live Match", [(home, 1.13), (away, 4.75)]),
            ("Face à Face - Live 2ème Set", [(home, 1.38), (away, 2.4)]),
            ("Face à Face - Live 2eme Jeu / 2ème Set", [(home, 3.2), (away, 1.2)]),
            ("Vainqueur du match", [(home, 1.1), (away, 7.0)]),
        ]:
            markets = normalize_unibet_market(label, odds, home, away)
            if is_victoire_market_label(label) and markets and markets[0].compare_key == "h2h":
                accepted.append(label)
            else:
                rejected.append(label)
        self.assertIn("Face à Face - Live Match", accepted)
        self.assertIn("Vainqueur du match", accepted)
        self.assertIn("Face à Face - Live 2eme Jeu / 2ème Set", rejected)
        self.assertIn("Face à Face - Live 2ème Set", rejected)


if __name__ == "__main__":
    unittest.main()
