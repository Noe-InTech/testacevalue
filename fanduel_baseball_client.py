"""Client FanDuel — baseball / MLB / KBO / NPB / CPBL."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from baseball_constants import (
    FANDUEL_BASEBALL_COMPETITION_IDS,
    FANDUEL_BASEBALL_EVENT_TABS,
    FANDUEL_BASEBALL_EVENT_TYPE_ID,
    FANDUEL_KBO_COMPETITION_ID,
    FANDUEL_MLB_COMPETITION_ID,
    FANDUEL_MLB_CONTENT_PAGE,
    FANDUEL_NPB_COMPETITION_ID,
)
from baseball_listings import competition_from_blob, looks_like_game_name
from fanduel_client import FanDuelClient


@dataclass(frozen=True)
class FanDuelBaseballEvent:
    event_id: str
    name: str
    home_team: str
    away_team: str
    open_date: str
    competition: str = "MLB"


def split_baseball_teams(name: str) -> tuple[str, str]:
    text = str(name or "").strip()
    # Strip pitcher annotations: "Team (P Name) @ Team (P Name)"
    text = re.sub(r"\s*\([^)]*\)", "", text).strip()
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


class FanDuelBaseballClient(FanDuelClient):
    def _events_from_payload(
        self,
        payload: dict[str, Any],
        *,
        competition_hint: str = "",
    ) -> list[FanDuelBaseballEvent]:
        events = (payload.get("attachments") or {}).get("events") or {}
        results: list[FanDuelBaseballEvent] = []
        for event_id, event in events.items():
            name = str(event.get("name", "")).strip()
            if not looks_like_game_name(name):
                continue
            home, away = split_baseball_teams(name)
            if not home or not away:
                continue
            competition = competition_hint or competition_from_blob(name)
            results.append(
                FanDuelBaseballEvent(
                    event_id=str(event_id),
                    name=name,
                    home_team=home,
                    away_team=away,
                    open_date=str(event.get("openDate", "")),
                    competition=competition,
                )
            )
        return results

    def _list_competition_events(
        self,
        competition_id: str,
        *,
        competition_hint: str = "",
    ) -> list[FanDuelBaseballEvent]:
        payload = self._get(
            "/api/competition-page",
            {
                "page": "COMPETITION",
                "competitionId": competition_id,
                "eventTypeId": FANDUEL_BASEBALL_EVENT_TYPE_ID,
            },
        )
        return self._events_from_payload(payload, competition_hint=competition_hint)

    def list_mlb_events(self) -> list[FanDuelBaseballEvent]:
        merged: dict[str, FanDuelBaseballEvent] = {}
        try:
            payload = self._get(
                "/api/content-managed-page",
                {
                    "page": "CUSTOM",
                    "customPageId": FANDUEL_MLB_CONTENT_PAGE,
                    "eventTypeId": FANDUEL_BASEBALL_EVENT_TYPE_ID,
                },
            )
            for event in self._events_from_payload(payload, competition_hint="MLB"):
                merged[event.event_id] = event
        except Exception:
            pass
        for event in self._list_competition_events(
            FANDUEL_MLB_COMPETITION_ID,
            competition_hint="MLB",
        ):
            merged[event.event_id] = event
        return sorted(merged.values(), key=lambda item: (item.open_date, item.name))

    def list_kbo_events(self) -> list[FanDuelBaseballEvent]:
        return self._list_competition_events(
            FANDUEL_KBO_COMPETITION_ID,
            competition_hint="KBO",
        )

    def list_npb_events(self) -> list[FanDuelBaseballEvent]:
        if not FANDUEL_NPB_COMPETITION_ID:
            return []
        return self._list_competition_events(
            FANDUEL_NPB_COMPETITION_ID,
            competition_hint="NPB",
        )

    def list_baseball_events(self) -> list[FanDuelBaseballEvent]:
        merged: dict[str, FanDuelBaseballEvent] = {}
        for event in self.list_mlb_events():
            merged[event.event_id] = event
        for event in self.list_kbo_events():
            merged[event.event_id] = event
        for event in self.list_npb_events():
            merged[event.event_id] = event
        # CPBL (+ future NPB) for FD-only inventory
        for competition_id in FANDUEL_BASEBALL_COMPETITION_IDS:
            if competition_id in {
                FANDUEL_MLB_COMPETITION_ID,
                FANDUEL_KBO_COMPETITION_ID,
                FANDUEL_NPB_COMPETITION_ID,
            }:
                continue
            try:
                for event in self._list_competition_events(
                    competition_id,
                    competition_hint="CPBL",
                ):
                    merged[event.event_id] = event
            except Exception:
                continue
        return sorted(merged.values(), key=lambda item: (item.open_date, item.name))

    def build_event_payload(self, event: FanDuelBaseballEvent) -> dict[str, Any]:
        markets = self.get_event_markets(
            event.event_id,
            tabs=FANDUEL_BASEBALL_EVENT_TABS,
            timeout=10.0,
        )
        return {
            "event_id": event.event_id,
            "event": event.name,
            "home_team": event.home_team,
            "away_team": event.away_team,
            "open_date": event.open_date,
            "competition": event.competition,
            "market_count": len(markets),
            "markets": markets,
        }
