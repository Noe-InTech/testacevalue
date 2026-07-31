"""Client FanDuel — football / soccer player props."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from fanduel_client import FanDuelClient, runner_fanduel_price_bundle
from soccer_constants import (
    FANDUEL_SOCCER_COMPETITION_IDS,
    FANDUEL_SOCCER_EVENT_TABS,
    FANDUEL_SOCCER_EVENT_TYPE_ID,
)


@dataclass(frozen=True)
class FanDuelSoccerEvent:
    event_id: str
    name: str
    home_team: str
    away_team: str
    open_date: str


def split_soccer_teams(name: str) -> tuple[str, str]:
    text = str(name or "").strip()
    if " @ " in text:
        away, home = text.split(" @ ", 1)
        return home.strip(), away.strip()
    if " v " in text:
        home, away = text.split(" v ", 1)
        return home.strip(), away.strip()
    if " vs " in text.lower():
        parts = re.split(r"\s+vs\s+", text, maxsplit=1, flags=re.I)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    return text, ""


class FanDuelSoccerClient(FanDuelClient):
    def _events_from_payload(self, payload: dict[str, Any]) -> list[FanDuelSoccerEvent]:
        events = (payload.get("attachments") or {}).get("events") or {}
        results: list[FanDuelSoccerEvent] = []
        for event_id, event in events.items():
            name = str(event.get("name", "")).strip()
            home, away = split_soccer_teams(name)
            if not home or not away:
                continue
            # skip futures shells
            if " v " not in name and " vs " not in name.lower() and " @ " not in name:
                continue
            results.append(
                FanDuelSoccerEvent(
                    event_id=str(event_id),
                    name=name,
                    home_team=home,
                    away_team=away,
                    open_date=str(event.get("openDate", "")),
                )
            )
        return results

    def list_soccer_events(
        self,
        competition_ids: tuple[str, ...] | None = None,
    ) -> list[FanDuelSoccerEvent]:
        ids = competition_ids or FANDUEL_SOCCER_COMPETITION_IDS
        merged: dict[str, FanDuelSoccerEvent] = {}
        for competition_id in ids:
            try:
                payload = self._get(
                    "/api/competition-page",
                    {
                        "page": "COMPETITION",
                        "competitionId": str(competition_id),
                        "eventTypeId": FANDUEL_SOCCER_EVENT_TYPE_ID,
                    },
                )
            except RuntimeError:
                continue
            for event in self._events_from_payload(payload):
                merged[event.event_id] = event
        return sorted(merged.values(), key=lambda e: e.open_date)

    def get_event_payload(self, event_id: str) -> dict[str, Any]:
        merged_markets: dict[str, dict[str, Any]] = {}
        event_meta: dict[str, Any] = {}
        for tab in FANDUEL_SOCCER_EVENT_TABS:
            try:
                payload = self._get(
                    "/api/event-page",
                    {"eventId": str(event_id), "tab": tab},
                )
            except RuntimeError:
                continue
            attachments = payload.get("attachments") or {}
            events = attachments.get("events") or {}
            if not event_meta and events:
                event_meta = next(iter(events.values()))
            for market_id, market in (attachments.get("markets") or {}).items():
                if isinstance(market, dict):
                    merged_markets[str(market_id)] = market
        name = str(event_meta.get("name") or "")
        home, away = split_soccer_teams(name)
        return {
            "event_id": str(event_id),
            "name": name,
            "home_team": home,
            "away_team": away,
            "open_date": str(event_meta.get("openDate") or ""),
            "markets": list(merged_markets.values()),
        }

    @staticmethod
    def runner_bundle(runner: dict[str, Any]) -> dict[str, Any] | None:
        return runner_fanduel_price_bundle(runner)
