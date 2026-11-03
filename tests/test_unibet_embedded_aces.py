import unittest

from tennis_books_mapping import normalize_unibet_market
from unibet_client import UnibetClient


class UnibetEmbeddedAcesTests(unittest.TestCase):
    def test_embedded_aces_do_not_mix_market_titles_into_outcomes(self) -> None:
        html = (
            '{"id":1,"description":"Plus 4,5","price":"1,55","spread":4.5,'
            '"marketDesc":"Plus / Moins (Aces) - P.Udvardy 4,5 - Match"}'
            '{"id":2,"description":"Moins 4,5","price":"1,01","spread":4.5,'
            '"marketDesc":"Plus / Moins (Aces) - P.Udvardy 4,5 - Match"}'
            '{"id":3,"description":"Plus 6,5","price":"1,65","spread":6.5,'
            '"marketDesc":"Plus / Moins (Aces) - R.Montgomery 6,5 - Match"}'
        )
        client = UnibetClient()
        markets = client.extract_embedded_markets_from_html(html)
        udvardy = next(m for m in markets if "Udvardy" in m.label)
        labels = [outcome.label for outcome in udvardy.outcomes]
        self.assertEqual(labels, ["Plus 4,5", "Moins 4,5"])
        self.assertFalse(any("Montgomery" in label for label in labels))

        norm = normalize_unibet_market(
            udvardy.label,
            [(o.label, o.odds) for o in udvardy.outcomes],
            "P.Udvardy",
            "R.Montgomery",
        )
        self.assertEqual(len(norm), 1)
        self.assertEqual(norm[0].compare_key, "aces_player|udvardy|4.5")

    def test_events_detail_spread_formats_plus_moins_line(self) -> None:
        html = (
            '<script type="application/json">'
            '{"EventsDetail":{"events":[{"groupedMarkets":[{"description":"Total",'
            '"markets":[{"marketDesc":"Plus / Moins 230.5 Point(s) - Match","outcomes":['
            '{"id":1,"description":"Plus","price":"1,72","spread":230.5},'
            '{"id":2,"description":"Moins","price":"1,72","spread":230.5}'
            "]}]}]}]}}"
            "</script>"
        )
        markets = UnibetClient().extract_events_detail_markets_from_html(html)
        self.assertEqual(len(markets), 1)
        labels = [o.label for o in markets[0].outcomes]
        self.assertIn("Plus 230.5", labels)
        self.assertIn("Moins 230.5", labels)


if __name__ == "__main__":
    unittest.main()
