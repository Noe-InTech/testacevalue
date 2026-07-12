import unittest
from unittest import mock

from unibet_client import UnibetClient


class UnibetUrlMergeTests(unittest.TestCase):
    def test_event_fetch_urls_prefers_prematch(self) -> None:
        client = UnibetClient()
        meta = {
            "url": "https://www.unibet.fr/paris-en-direct/3363877/j-sinner-vs-a-zverev",
            "urls": [
                "https://www.unibet.fr/paris-en-direct/3363877/j-sinner-vs-a-zverev",
                "https://www.unibet.fr/paris-tennis/atp/wimbledon-h/3363877/j-sinner-vs-a-zverev",
            ],
        }
        ordered = client.event_fetch_urls(meta)
        self.assertLess(
            ordered.index(meta["urls"][1]),
            ordered.index(meta["urls"][0]),
        )

    def test_derive_prematch_urls_from_live(self) -> None:
        client = UnibetClient()
        with mock.patch.object(
            client,
            "list_tennis_competition_paths",
            return_value=["/paris-tennis/atp/wimbledon-h"],
        ):
            derived = client.derive_prematch_urls(
                "https://www.unibet.fr/paris-en-direct/99/foo-vs-bar"
            )
        self.assertIn("https://www.unibet.fr/paris-tennis/atp/wimbledon-h/99/foo-vs-bar", derived)


if __name__ == "__main__":
    unittest.main()
