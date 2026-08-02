import unittest

from book_urls import attach_fr_book_urls, bookmaker_to_key, resolve_fr_book_url


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

    def test_attach_fr_book_urls(self) -> None:
        rows = [
            {"bookmaker_fr": "Winamax", "match": "A vs B"},
            {"best_fr_bookmaker": "Unibet", "match": "C vs D"},
            {"bookmaker_fr": "", "match": "E vs F"},
        ]
        attach_fr_book_urls(
            rows,
            urls={
                "winamax": "https://www.winamax.fr/paris-sportifs/match/1",
                "unibet": "https://www.unibet.fr/paris/tennis/x",
            },
        )
        self.assertEqual(rows[0]["url_fr"], "https://www.winamax.fr/paris-sportifs/match/1")
        self.assertEqual(rows[1]["url_fr"], "https://www.unibet.fr/paris/tennis/x")
        self.assertEqual(rows[2]["url_fr"], "")


if __name__ == "__main__":
    unittest.main()
