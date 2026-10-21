"""Tests Winamax basketball — filtre props joueur (perf NBA)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from winamax_basketball_client import WinamaxBasketballClient, WinamaxBasketballMatchLink
from winamax_client import WinamaxMarket, WinamaxOutcome


def _market(label: str) -> WinamaxMarket:
    return WinamaxMarket(
        label=label,
        outcomes=(
            WinamaxOutcome(label="Plus de", odds=1.85, selection_id="1"),
            WinamaxOutcome(label="Moins de", odds=1.90, selection_id="2"),
        ),
    )


class WinamaxBasketballPlayerPropFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = WinamaxBasketballClient(fetch_timeout=1)
        self.link = WinamaxBasketballMatchLink(
            match_id="123",
            url="https://www.winamax.fr/paris-sportifs/match/123",
            title="Lakers - Celtics",
            home_team="Lakers",
            away_team="Celtics",
            start_date="2026-10-21T00:00:00Z",
            competition="NBA",
        )

    def test_build_event_payload_keeps_only_player_props(self) -> None:
        raw = [
            _market("Vainqueur du match"),
            _market("Handicap - Lakers (-5.5)"),
            _market("Nombre de points du joueur - LeBron James (25.5)"),
            _market("Nombre de rebonds du joueur - Anthony Davis (10.5)"),
            _market("Total de points - match"),
        ]
        with (
            patch.object(self.client, "fetch_route", return_value={"players": {}}),
            patch.object(self.client, "extract_markets_from_payload", return_value=raw),
        ):
            payload = self.client.build_event_payload(self.link)

        labels = [m["label"] for m in payload["markets"]]
        self.assertEqual(payload["market_count"], 2)
        self.assertEqual(
            labels,
            [
                "Nombre de points du joueur - LeBron James (25.5)",
                "Nombre de rebonds du joueur - Anthony Davis (10.5)",
            ],
        )


if __name__ == "__main__":
    unittest.main()
