"""Fusion d'ancres basketball quand les books utilisent des libellés d'équipes différents."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from book_urls import attach_fr_book_urls
from compare_wnba_props_vs_fanduel import discover_anchors, teams_match
from basketball_anchor import attach_basketball_anchor, resolve_merged_anchor_key


class DiscoverAnchorsMergeTests(unittest.TestCase):
    def test_winamax_merges_with_unibet_fanduel_abbreviated_teams(self) -> None:
        unibet = [
            SimpleNamespace(
                home_team="Det Pistons",
                away_team="Bos Celtics",
                event_id="u1",
                url="https://unibet.example/u1",
            )
        ]
        winamax = [
            SimpleNamespace(
                home_team="Detroit Pistons",
                away_team="Boston Celtics",
                match_id="w1",
                url="https://winamax.example/w1",
                status="",
            )
        ]
        fanduel = [
            SimpleNamespace(
                home_team="Detroit Pistons",
                away_team="Boston Celtics",
                event_id="f1",
            )
        ]
        anchors = discover_anchors(
            unibet_events=unibet,
            betclic_links=[],
            winamax_links=winamax,
            fanduel_events=fanduel,
        )
        self.assertEqual(len(anchors), 1)
        anchor = anchors[0]
        self.assertEqual(anchor["unibet_event_id"], "u1")
        self.assertEqual(anchor["winamax_match_id"], "w1")
        self.assertEqual(anchor["fanduel_event_id"], "f1")
        self.assertEqual(anchor["sources"], {"unibet", "winamax", "fanduel"})
        self.assertEqual(anchor["urls"]["winamax"], "https://winamax.example/w1")
        self.assertEqual(anchor["match"], "Detroit Pistons vs Boston Celtics")

    def test_betclic_merges_with_abbreviated_unibet(self) -> None:
        betclic = [
            SimpleNamespace(
                home_team="Detroit Pistons",
                away_team="Boston Celtics",
                match_id="b1",
                url="https://betclic.example/m-b1",
            )
        ]
        unibet = [
            SimpleNamespace(
                home_team="Det Pistons",
                away_team="Bos Celtics",
                event_id="u1",
                url="https://unibet.example/u1",
            )
        ]
        anchors = discover_anchors(
            unibet_events=unibet,
            betclic_links=betclic,
            winamax_links=[],
            fanduel_events=[],
        )
        self.assertEqual(len(anchors), 1)
        self.assertEqual(anchors[0]["betclic_match_id"], "b1")
        self.assertEqual(anchors[0]["unibet_event_id"], "u1")

    def test_winamax_listed_first_still_merges(self) -> None:
        winamax = [
            SimpleNamespace(
                home_team="Los Angeles Lakers",
                away_team="Golden State Warriors",
                match_id="w9",
                url="https://winamax.example/w9",
                status="",
            )
        ]
        fanduel = [
            SimpleNamespace(
                home_team="LA Lakers",
                away_team="GS Warriors",
                event_id="f9",
            )
        ]
        anchors = discover_anchors(
            unibet_events=[],
            betclic_links=[],
            winamax_links=winamax,
            fanduel_events=fanduel,
        )
        self.assertEqual(len(anchors), 1)
        self.assertEqual(anchors[0]["winamax_match_id"], "w9")
        self.assertEqual(anchors[0]["fanduel_event_id"], "f9")

    def test_swapped_home_away_matches(self) -> None:
        anchors: dict = {}
        attach_basketball_anchor(
            anchors,
            "Team A",
            "Team B",
            teams_match=teams_match,
        )
        key = resolve_merged_anchor_key(
            anchors,
            "Team B",
            "Team A",
            teams_match=teams_match,
        )
        self.assertEqual(len(anchors), 1)
        self.assertIn(key, anchors)

    def test_fr_book_url_fallback_when_book_events_empty(self) -> None:
        rows = [
            {
                "bookmaker_fr": "Winamax",
                "selection_id": "1:2",
                "fr_book_url": "https://www.winamax.fr/paris-sportifs/match/42",
                "fr_book_match_id": "42",
            }
        ]
        attach_fr_book_urls(
            rows,
            urls={"winamax": "https://www.winamax.fr/paris-sportifs/match/99"},
            book_events={},
            resolve_betclic_share=False,
        )
        self.assertEqual(rows[0]["url_fr_kind"], "selection")
        self.assertIn("match=42", rows[0]["url_fr"])

    def test_anchor_urls_fallback_when_payload_missing_from_book_events(self) -> None:
        rows = [
            {
                "bookmaker_fr": "Betclic",
                "selection_id": "10:20",
            }
        ]
        attach_fr_book_urls(
            rows,
            urls={"betclic": "https://www.betclic.fr/match-m555"},
            book_events={"betclic": {"markets": []}},
            resolve_betclic_share=False,
        )
        self.assertIn("/go/betclic?", rows[0]["url_fr"])
        self.assertIn("m=555", rows[0]["url_fr"])


if __name__ == "__main__":
    unittest.main()
