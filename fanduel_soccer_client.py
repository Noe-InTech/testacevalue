"""Client FanDuel — football / soccer player props."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    competition_id: str = ""
    competition_name: str = ""


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
    def _events_from_payload(
        self,
        payload: dict[str, Any],
        *,
        competition_id: str = "",
        competition_name: str = "",
    ) -> list[FanDuelSoccerEvent]:
        attachments = payload.get("attachments") or {}
        events = attachments.get("events") or {}
        competitions = attachments.get("competitions") or {}
        results: list[FanDuelSoccerEvent] = []
        for event_id, event in events.items():
            if not isinstance(event, dict):
                continue
            name = str(event.get("name", "")).strip()
            home, away = split_soccer_teams(name)
            if not home or not away:
                continue
            if " v " not in name and " vs " not in name.lower() and " @ " not in name:
                continue
            cid = competition_id or str(event.get("competitionId") or "")
            cname = competition_name
            if not cname and cid and isinstance(competitions.get(cid), dict):
                cname = str(competitions[cid].get("name") or "")
            elif not cname and cid and isinstance(competitions.get(str(cid)), dict):
                cname = str(competitions[str(cid)].get("name") or "")
            results.append(
                FanDuelSoccerEvent(
                    event_id=str(event_id),
                    name=name,
                    home_team=home,
                    away_team=away,
                    open_date=str(event.get("openDate", "")),
                    competition_id=cid,
                    competition_name=cname,
                )
            )
        return results

    def discover_soccer_competition_ids(self) -> tuple[str, ...]:
        """Toutes les compétitions foot actuelles via page SPORT."""
        try:
            payload = self._get(
                "/api/content-managed-page",
                {"page": "SPORT", "eventTypeId": FANDUEL_SOCCER_EVENT_TYPE_ID},
            )
        except RuntimeError:
            return FANDUEL_SOCCER_COMPETITION_IDS
        competitions = (payload.get("attachments") or {}).get("competitions") or {}
        ids = tuple(str(cid) for cid in competitions.keys())
        if not ids:
            return FANDUEL_SOCCER_COMPETITION_IDS
        # Merge whitelist in case SPORT omits some
        merged = list(dict.fromkeys([*ids, *FANDUEL_SOCCER_COMPETITION_IDS]))
        return tuple(merged)

    def list_soccer_events(
        self,
        competition_ids: tuple[str, ...] | None = None,
        *,
        discover: bool = True,
    ) -> list[FanDuelSoccerEvent]:
        merged: dict[str, FanDuelSoccerEvent] = {}

        # Absorb events already listed on the SPORT page (fast path).
        if discover and competition_ids is None:
            try:
                sport_payload = self._get(
                    "/api/content-managed-page",
                    {"page": "SPORT", "eventTypeId": FANDUEL_SOCCER_EVENT_TYPE_ID},
                )
                competitions = (sport_payload.get("attachments") or {}).get("competitions") or {}
                for event in self._events_from_payload(sport_payload):
                    merged[event.event_id] = event
                ids = tuple(str(cid) for cid in competitions.keys()) or FANDUEL_SOCCER_COMPETITION_IDS
                # Keep whitelist extras
                ids = tuple(dict.fromkeys([*ids, *FANDUEL_SOCCER_COMPETITION_IDS]))
            except RuntimeError:
                ids = FANDUEL_SOCCER_COMPETITION_IDS
        else:
            ids = competition_ids or FANDUEL_SOCCER_COMPETITION_IDS

        def fetch_comp(competition_id: str) -> list[FanDuelSoccerEvent]:
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
                return []
            comps = (payload.get("attachments") or {}).get("competitions") or {}
            cname = ""
            if str(competition_id) in comps and isinstance(comps[str(competition_id)], dict):
                cname = str(comps[str(competition_id)].get("name") or "")
            return self._events_from_payload(
                payload,
                competition_id=str(competition_id),
                competition_name=cname,
            )

        with ThreadPoolExecutor(max_workers=6) as pool:
            futs = [pool.submit(fetch_comp, cid) for cid in ids]
            for fut in as_completed(futs):
                for event in fut.result():
                    merged[event.event_id] = event
        return sorted(merged.values(), key=lambda e: e.open_date)

    def get_event_payload(self, event_id: str) -> dict[str, Any]:
        merged_markets: dict[str, dict[str, Any]] = {}
        event_meta: dict[str, Any] = {}

        def fetch_tab(tab: str) -> dict[str, Any] | None:
            try:
                return self._get(
                    "/api/event-page",
                    {"eventId": str(event_id), "tab": tab},
                )
            except RuntimeError:
                return None

        with ThreadPoolExecutor(max_workers=len(FANDUEL_SOCCER_EVENT_TABS)) as pool:
            payloads = list(pool.map(fetch_tab, FANDUEL_SOCCER_EVENT_TABS))

        for payload in payloads:
            if not payload:
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
