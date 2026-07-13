"""Client FanDuel — basketball / WNBA (séparé du client tennis)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from basketball_constants import (
    FANDUEL_BASKETBALL_EVENT_TYPE_ID,
    FANDUEL_NBA_COMPETITION_ID,
    FANDUEL_NBA_CONTENT_PAGE,
    FANDUEL_NBA_EVENT_TABS,
    FANDUEL_WNBA_COMPETITION_ID,
    FANDUEL_WNBA_EVENT_TABS,
)
from fanduel_client import FanDuelClient


@dataclass(frozen=True)
class FanDuelBasketballEvent:
    event_id: str
    name: str
    home_team: str
    away_team: str
    open_date: str


def split_basketball_teams(name: str) -> tuple[str, str]:
    text = str(name or "").strip()
    if " @ " in text:
        away, home = text.split(" @ ", 1)
        return home.strip(), away.strip()
    if " at " in text.lower():
        parts = re.split(r"\s+at\s+", text, maxsplit=1, flags=re.I)
        if len(parts) == 2:
            return parts[1].strip(), parts[0].strip()
    if " v " in text:
        left, right = text.split(" v ", 1)
        return left.strip(), right.strip()
    if " vs " in text.lower():
        parts = re.split(r"\s+vs\s+", text, maxsplit=1, flags=re.I)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    return text, ""


class FanDuelBasketballClient(FanDuelClient):
    def _events_from_payload(self, payload: dict[str, Any]) -> list[FanDuelBasketballEvent]:
        events = (payload.get("attachments") or {}).get("events") or {}
        results: list[FanDuelBasketballEvent] = []
        for event_id, event in events.items():
            name = str(event.get("name", "")).strip()
            home, away = split_basketball_teams(name)
            if not home or not away:
                continue
            results.append(
                FanDuelBasketballEvent(
                    event_id=str(event_id),
                    name=name,
                    home_team=home,
                    away_team=away,
                    open_date=str(event.get("openDate", "")),
                )
            )
        return results

    def _list_competition_events(self, competition_id: str) -> list[FanDuelBasketballEvent]:
        payload = self._get(
            "/api/competition-page",
            {
                "page": "COMPETITION",
                "competitionId": competition_id,
                "eventTypeId": FANDUEL_BASKETBALL_EVENT_TYPE_ID,
            },
        )
        return self._events_from_payload(payload)

    def _list_content_page_events(self, page_id: str) -> list[FanDuelBasketballEvent]:
        payload = self._get(
            "/api/content-managed-page",
            {
                "page": "CUSTOM",
                "customPageId": page_id,
                "eventTypeId": FANDUEL_BASKETBALL_EVENT_TYPE_ID,
            },
        )
        return self._events_from_payload(payload)

    def list_wnba_events(self) -> list[FanDuelBasketballEvent]:
        return self._list_competition_events(FANDUEL_WNBA_COMPETITION_ID)

    def list_nba_events(self) -> list[FanDuelBasketballEvent]:
        events = self._list_competition_events(FANDUEL_NBA_COMPETITION_ID)
        if events:
            return events
        return self._list_content_page_events(FANDUEL_NBA_CONTENT_PAGE)

    def build_event_payload(
        self,
        event: FanDuelBasketballEvent,
        *,
        tabs: tuple[str, ...] = FANDUEL_WNBA_EVENT_TABS,
    ) -> dict[str, Any]:
        markets = self.get_event_markets(event.event_id, tabs=tabs)
        return {
            "event_id": event.event_id,
            "event": event.name,
            "home_team": event.home_team,
            "away_team": event.away_team,
            "open_date": event.open_date,
            "market_count": len(markets),
            "markets": markets,
        }

    def build_nba_event_payload(self, event: FanDuelBasketballEvent) -> dict[str, Any]:
        return self.build_event_payload(event, tabs=FANDUEL_NBA_EVENT_TABS)
