import unittest

from book_urls import (
    attach_fr_book_urls,
    bookmaker_to_key,
    build_fr_book_url,
    resolve_fr_book_url,
    selection_id_for_normalized_outcome,
)
from unibet_client import UnibetClient


class BookUrlTests(unittest.TestCase):
    def test_bookmaker_to_key(self) -> None:
        self.assertEqual(bookmaker_to_key("Betclic"), "betclic")
        self.assertEqual(bookmaker_to_key("Unibet"), "unibet")
        self.assertEqual(bookmaker_to_key("Winamax"), "winamax")
        self.assertEqual(bookmaker_to_key(""), "")

    def test_resolve_prefers_book_events(self) -> None:
        url = resolve_fr_book_url(
            "Betclic",
            urls={"betclic": "https://example.com/from-urls"},
            book_events={"betclic": {"url": "https://example.com/from-event"}},
        )
        self.assertEqual(url, "https://example.com/from-event")

    def test_build_unibet_selection_deep_link(self) -> None:
        url = build_fr_book_url(
            "Unibet",
            "https://www.unibet.fr/paris-tennis/atp/1/match",
            selection_id="123456789",
        )
        self.assertEqual(
            url,
            "https://www.unibet.fr/paris-tennis/atp/1/match?outcomeIds=123456789",
        )

    def test_build_non_unibet_keeps_match_url(self) -> None:
        url = build_fr_book_url(
            "Winamax",
            "https://www.winamax.fr/paris-sportifs/match/1",
            selection_id="999",
        )
        self.assertEqual(url, "https://www.winamax.fr/paris-sportifs/match/1")

    def test_selection_id_for_over_under(self) -> None:
        sid = selection_id_for_normalized_outcome(
            normalized_outcome="Over",
            raw_outcomes=[("Plus de 7,5", 1.85), ("Moins de 7,5", 1.95)],
            selection_ids={"Plus de 7,5": "111", "Moins de 7,5": "222"},
        )
        self.assertEqual(sid, "111")
        sid_under = selection_id_for_normalized_outcome(
            normalized_outcome="Under",
            raw_outcomes=[("Plus de 7,5", 1.85), ("Moins de 7,5", 1.95)],
            selection_ids={"Plus de 7,5": "111", "Moins de 7,5": "222"},
        )
        self.assertEqual(sid_under, "222")

    def test_attach_fr_book_urls(self) -> None:
        rows = [
            {"bookmaker_fr": "Winamax", "match": "A vs B"},
            {"best_fr_bookmaker": "Unibet", "match": "C vs D"},
            {
                "bookmaker_fr": "Unibet",
                "match": "E vs F",
                "selection_id": "555",
            },
            {"bookmaker_fr": "", "match": "G vs H"},
        ]
        attach_fr_book_urls(
            rows,
            urls={
                "winamax": "https://www.winamax.fr/paris-sportifs/match/1",
                "unibet": "https://www.unibet.fr/paris/tennis/x",
            },
        )
        self.assertEqual(rows[0]["url_fr"], "https://www.winamax.fr/paris-sportifs/match/1")
        self.assertEqual(rows[0]["url_fr_kind"], "match")
        self.assertEqual(rows[1]["url_fr"], "https://www.unibet.fr/paris/tennis/x")
        self.assertEqual(rows[1]["url_fr_kind"], "match")
        self.assertEqual(
            rows[2]["url_fr"],
            "https://www.unibet.fr/paris/tennis/x?outcomeIds=555",
        )
        self.assertEqual(rows[2]["url_fr_kind"], "selection")
        self.assertEqual(rows[3]["url_fr"], "")


class UnibetSelectionCatalogTests(unittest.TestCase):
    def test_extract_selection_catalog(self) -> None:
        html = (
            '{"id":987654321,"description":"Plus de 7,5","parent":"m1","pos":1,'
            '"price":"1.85","foo":1,"marketDesc":"Nombre d\'aces"}'
        )
        catalog = UnibetClient().extract_selection_catalog(html)
        self.assertIn(("Nombre d'aces", "Plus de 7,5"), catalog)
        selection_id, odds = catalog[("Nombre d'aces", "Plus de 7,5")]
        self.assertEqual(selection_id, "987654321")
        self.assertEqual(odds, 1.85)


if __name__ == "__main__":
    unittest.main()
