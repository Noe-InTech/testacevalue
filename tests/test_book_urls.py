import unittest
from unittest.mock import patch

from book_urls import (
    attach_fr_book_urls,
    bookmaker_to_key,
    build_fr_book_url,
    resolve_fr_book_url,
    selection_id_for_normalized_outcome,
    split_compound_selection_id,
)
from unibet_client import UnibetClient
from winamax_client import WinamaxClient, WinamaxOutcome, WinamaxMarket
from betclic_client import BetclicClient, BetclicOutcome, BetclicMarket


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
            "/go/unibet?o=123456789&u=https%3A%2F%2Fwww.unibet.fr%2Fparis-tennis%2Fatp%2F1%2Fmatch",
        )

    def test_build_winamax_selection_deep_link(self) -> None:
        url = build_fr_book_url(
            "Winamax",
            "https://www.winamax.fr/paris-sportifs/match/73062274",
            selection_id="672502908:2090722078",
            match_id="73062274",
        )
        self.assertEqual(
            url,
            "/go/winamax?match=73062274&b=672502908&o=2090722078",
        )

    def test_build_winamax_without_compound_id_keeps_match_url(self) -> None:
        url = build_fr_book_url(
            "Winamax",
            "https://www.winamax.fr/paris-sportifs/match/1",
            selection_id="999",
        )
        self.assertEqual(url, "https://www.winamax.fr/paris-sportifs/match/1")

    def test_build_betclic_share_deep_link(self) -> None:
        def fake_share(selection_id: str, match_id: str, market_id: str) -> str:
            self.assertEqual(selection_id, "111")
            self.assertEqual(match_id, "222")
            self.assertEqual(market_id, "333")
            return "https://www.betclic.fr/bet/token-abc"

        url = build_fr_book_url(
            "Betclic",
            "https://www.betclic.fr/tennis-stennis/foo-m222",
            selection_id="111:333",
            match_id="222",
            resolve_betclic_share=fake_share,
        )
        self.assertIn("/go/betclic?", url)
        self.assertIn("s=111", url)
        self.assertIn("m=222", url)
        self.assertIn("k=333", url)
        self.assertIn("url=https%3A%2F%2Fwww.betclic.fr%2Fbet%2Ftoken-abc", url)

    def test_build_betclic_without_share_resolver_keeps_bridge(self) -> None:
        url = build_fr_book_url(
            "Betclic",
            "https://www.betclic.fr/tennis-stennis/foo-m222",
            selection_id="111:333",
            match_id="222",
        )
        self.assertIn("/go/betclic?", url)
        self.assertIn("s=111", url)
        self.assertNotIn("url=", url)

    def test_split_compound_selection_id(self) -> None:
        self.assertEqual(split_compound_selection_id("a:b"), ("a", "b"))
        self.assertEqual(split_compound_selection_id("plain"), ("", ""))

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

    def test_selection_id_for_yes_player_prop(self) -> None:
        """Baseball/soccer: raw outcomes are player names, normalized issue is Yes."""
        sid = selection_id_for_normalized_outcome(
            normalized_outcome="Yes",
            raw_outcomes=[
                ("Christian Yelich", 2.15),
                ("William Contreras", 1.90),
            ],
            selection_ids={
                "Christian Yelich": "10:20",
                "William Contreras": "11:21",
            },
            player_name="Christian Yelich",
        )
        self.assertEqual(sid, "10:20")

    def test_selection_id_for_yes_oui_alias(self) -> None:
        sid = selection_id_for_normalized_outcome(
            normalized_outcome="Yes",
            raw_outcomes=[("Oui", 1.80), ("Non", 1.95)],
            selection_ids={"Oui": "aaa:bbb", "Non": "ccc:ddd"},
        )
        self.assertEqual(sid, "aaa:bbb")

    def test_selection_id_for_yes_player_with_tier_suffix(self) -> None:
        sid = selection_id_for_normalized_outcome(
            normalized_outcome="Yes",
            raw_outcomes=[("Contreras, Willson 1+", 1.75), ("Yelich, Christian 1+", 2.10)],
            selection_ids={
                "Contreras, Willson 1+": "1:2",
                "Yelich, Christian 1+": "3:4",
            },
            player_name="Christian Yelich",
        )
        self.assertEqual(sid, "3:4")

    def test_selection_id_disambiguates_player_tiers(self) -> None:
        raw = [("Yelich, Christian 2+", 40.0), ("Yelich, Christian 1+", 7.0)]
        ids = {
            "Yelich, Christian 2+": "702504346",
            "Yelich, Christian 1+": "702504347",
        }
        sid_1 = selection_id_for_normalized_outcome(
            normalized_outcome="Yes",
            raw_outcomes=raw,
            selection_ids=ids,
            player_name="Christian Yelich",
            line="",
        )
        sid_2 = selection_id_for_normalized_outcome(
            normalized_outcome="Yes",
            raw_outcomes=raw,
            selection_ids=ids,
            player_name="Christian Yelich",
            line="2",
        )
        self.assertEqual(sid_1, "702504347")
        self.assertEqual(sid_2, "702504346")

    def test_selection_id_for_home_away_team_alias(self) -> None:
        sid = selection_id_for_normalized_outcome(
            normalized_outcome="home",
            raw_outcomes=[("LA Angels", 2.9), ("MIL Brewers", 1.42)],
            selection_ids={"LA Angels": "111", "MIL Brewers": "222"},
            home="Los Angeles Angels",
            away="Milwaukee Brewers",
        )
        self.assertEqual(sid, "111")

    def test_attach_fr_book_urls(self) -> None:
        rows = [
            {
                "bookmaker_fr": "Winamax",
                "match": "A vs B",
                "selection_id": "10:20",
            },
            {"best_fr_bookmaker": "Unibet", "match": "C vs D"},
            {
                "bookmaker_fr": "Unibet",
                "match": "E vs F",
                "selection_id": "555",
            },
            {
                "bookmaker_fr": "Betclic",
                "match": "G vs H",
                "selection_id": "111:333",
            },
            {"bookmaker_fr": "", "match": "I vs J"},
        ]
        attach_fr_book_urls(
            rows,
            urls={
                "winamax": "https://www.winamax.fr/paris-sportifs/match/1",
                "unibet": "https://www.unibet.fr/paris/tennis/x",
                "betclic": "https://www.betclic.fr/tennis-stennis/foo-m222",
            },
            book_events={
                "betclic": {
                    "url": "https://www.betclic.fr/tennis-stennis/foo-m222",
                    "match_id": "222",
                }
            },
            resolve_betclic_share=lambda s, m, k: "https://www.betclic.fr/bet/tok",
        )
        self.assertEqual(
            rows[0]["url_fr"],
            "/go/winamax?match=1&b=10&o=20",
        )
        self.assertEqual(rows[0]["url_fr_kind"], "selection")
        self.assertEqual(
            rows[0]["url_fr_web"],
            "https://www.winamax.fr/paris-sportifs/match/1#b=10&o=20",
        )
        self.assertEqual(rows[1]["url_fr"], "https://www.unibet.fr/paris/tennis/x")
        self.assertEqual(rows[1]["url_fr_kind"], "match")
        self.assertEqual(
            rows[2]["url_fr"],
            "/go/unibet?o=555&u=https%3A%2F%2Fwww.unibet.fr%2Fparis%2Ftennis%2Fx",
        )
        self.assertEqual(rows[2]["url_fr_kind"], "selection")
        self.assertEqual(
            rows[2]["url_fr_web"],
            "https://www.unibet.fr/paris/tennis/x?outcomeIds=555",
        )
        self.assertIn("/go/betclic?", rows[3]["url_fr"])
        self.assertIn("url=https%3A%2F%2Fwww.betclic.fr%2Fbet%2Ftok", rows[3]["url_fr"])
        self.assertEqual(rows[3]["url_fr_kind"], "selection")
        self.assertEqual(rows[4]["url_fr"], "")


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


class WinamaxSelectionIdTests(unittest.TestCase):
    def test_markets_to_payload_includes_selection_ids(self) -> None:
        markets = [
            WinamaxMarket(
                label="Vainqueur",
                outcomes=(
                    WinamaxOutcome("A", 1.5, selection_id="10:20"),
                    WinamaxOutcome("B", 2.5, selection_id="10:21"),
                ),
            )
        ]
        payload = WinamaxClient.markets_to_payload(markets)
        self.assertEqual(
            payload[0]["selection_ids"],
            {"A": "10:20", "B": "10:21"},
        )

    def test_extract_markets_keeps_bet_and_outcome_ids(self) -> None:
        client = WinamaxClient()
        payload = {
            "bets": {
                "100": {
                    "betId": 100,
                    "matchId": "55",
                    "betTitle": "Vainqueur",
                    "available": True,
                    "outcomes": [1, 2],
                }
            },
            "outcomes": {
                "1": {"label": "Home"},
                "2": {"label": "Away"},
            },
            "odds": {"1": 1.8, "2": 2.1},
        }
        markets = client.extract_markets_from_payload(payload, "55")
        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0].outcomes[0].selection_id, "100:1")
        self.assertEqual(markets[0].outcomes[1].selection_id, "100:2")


class BetclicSelectionIdTests(unittest.TestCase):
    def test_markets_to_payload_includes_selection_ids(self) -> None:
        markets = [
            BetclicMarket(
                label="Vainqueur",
                outcomes=(
                    BetclicOutcome("A", 1.5, selection_id="11:22"),
                    BetclicOutcome("B", 2.5, selection_id="12:22"),
                ),
            )
        ]
        payload = BetclicClient.markets_to_payload(markets)
        self.assertEqual(
            payload[0]["selection_ids"],
            {"A": "11:22", "B": "12:22"},
        )

    def test_collect_outcomes_encodes_selection_and_market(self) -> None:
        market = {
            "id": "999",
            "name": "Vainqueur",
            "mainSelections": [
                {
                    "id": "111",
                    "name": "Home",
                    "odds": 1.7,
                    "status": 1,
                    "betslipMarketId": "222",
                }
            ],
        }
        outcomes = BetclicClient._collect_market_outcomes(market)
        self.assertEqual(outcomes[0].selection_id, "111:222")

    def test_create_share_url(self) -> None:
        client = BetclicClient()

        class FakeResponse:
            status_code = 200

            @staticmethod
            def json() -> dict:
                return {"token": "abc123"}

            text = ""

        with patch.object(client.session, "get", return_value=FakeResponse()), patch.object(
            client.session, "post", return_value=FakeResponse()
        ) as post:
            url = client.create_share_url(
                selection_id="111",
                match_id="222",
                market_id="333",
            )
        self.assertEqual(url, "https://www.betclic.fr/bet/abc123")
        args, kwargs = post.call_args
        self.assertIn("/sports-betting/api/v3/bets/share", args[0])
        self.assertEqual(
            kwargs["json"],
            {
                "selection_identifiers": [
                    {"selection_id": "111", "match_id": 222, "market_id": 333}
                ]
            },
        )


if __name__ == "__main__":
    unittest.main()
