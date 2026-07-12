"""Client pour l'API interne sbapi.sportsbook.fanduel.com."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Iterable

import requests

DEFAULT_AK = "FhMFpcPWXMeyZxOx"
DEFAULT_HOST = "https://sbapi.nj.sportsbook.fanduel.com"
DEFAULT_PAGE_IDS = ("wimbledon",)
DEFAULT_TENNIS_PAGE_CANDIDATES = (
    "wimbledon",
    "wimbledon-simples-hommes",
    "wimbledon-simples-dames",
    "atp-wimbledon",
    "wta-wimbledon",
    "us-open",
    "french-open",
    "australian-open",
    "atp",
    "wta",
    "tennis",
)

BASE_QUERY = {
    "currencyCode": "USD",
    "exchangeLocale": "en_US",
    "includePrices": "true",
    "language": "en",
    "regionCode": "NAMERICA",
    "_ak": DEFAULT_AK,
}

EVENT_TABS = (
    "popular",
    "all-markets",
    "set-betting",
    "game-lines",
    "same-game-parlay-",
)

TENNIS_EVENT_TYPE_ID = "2"
ACES_EVENT_TABS = ("popular", "all-markets", "game-lines", "same-game-parlay-")


@dataclass(frozen=True)
class FanDuelEvent:
    event_id: str
    name: str
    open_date: str
    home_player: str
    away_player: str
    is_doubles: bool


def american_to_decimal_fr(price: int | float | None) -> float | None:
    """Convertit une moneyline US en cote decimale FR (2 decimales)."""
    if price in (None, 0):
        return None
    price = float(price)
    if price > 0:
        return round(1 + price / 100.0, 2)
    return round(1 + 100.0 / abs(price), 2)


def format_american_moneyline(price: int | float | None) -> str:
    if price in (None, 0):
        return ""
    value = int(round(float(price)))
    return f"+{value}" if value > 0 else str(value)


def format_french_decimal(odds: float | int | None) -> str:
    if odds in (None, ""):
        return ""
    return f"{float(odds):.2f}".replace(".", ",")


def runner_fanduel_price_bundle(runner: dict[str, Any]) -> dict[str, Any]:
    odds = runner.get("winRunnerOdds") or {}
    american_raw = ((odds.get("americanDisplayOdds") or {}).get("americanOdds"))
    american = int(float(american_raw)) if american_raw is not None else None
    decimal_raw = runner_decimal_odds(runner)
    if american is not None:
        decimal_fr = american_to_decimal_fr(american)
    elif decimal_raw is not None:
        decimal_fr = round(float(decimal_raw), 2)
    else:
        decimal_fr = None
    return {
        "american": american,
        "decimal_raw": decimal_raw,
        "decimal_fr": decimal_fr,
    }


def runner_decimal_odds(runner: dict[str, Any]) -> float | None:
    odds = runner.get("winRunnerOdds") or {}
    decimal = ((odds.get("trueOdds") or {}).get("decimalOdds") or {}).get("decimalOdds")
    if decimal is not None:
        return round(float(decimal), 4)
    american = ((odds.get("americanDisplayOdds") or {}).get("americanOdds"))
    if american is None:
        return None
    american = float(american)
    if american > 0:
        return round(1 + american / 100.0, 4)
    return round(1 + 100.0 / abs(american), 4)


def split_event_players(name: str) -> tuple[str, str]:
    if " v " in name:
        left, right = name.split(" v ", 1)
        return left.strip(), right.strip()
    if " vs " in name.lower():
        parts = re.split(r"\s+vs\s+", name, flags=re.I)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    return name.strip(), ""


def page_id_candidates_from_urls(page_urls: list[str]) -> tuple[str, ...]:
    candidates: set[str] = set()
    for url in page_urls:
        slug = url.rstrip("/").rsplit("/", 1)[-1].strip().lower()
        if not slug or slug == "tennis":
            continue
        candidates.add(slug)
        for suffix in ("-simples-hommes", "-simples-dames", "-2026", "-2025"):
            if slug.endswith(suffix):
                candidates.add(slug[: -len(suffix)])
        if slug.startswith("atp-") or slug.startswith("wta-"):
            candidates.add(slug.split("-", 1)[1])
    candidates.update(DEFAULT_TENNIS_PAGE_CANDIDATES)
    return tuple(sorted(candidates))


class FanDuelClient:
    def __init__(self, host: str = DEFAULT_HOST, ak: str = DEFAULT_AK):
        self.host = host.rstrip("/")
        self.ak = ak
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def _get(self, path: str, params: dict[str, Any] | None = None, *, timeout: float = 30.0) -> dict[str, Any]:
        query = {**BASE_QUERY, "_ak": self.ak, **(params or {})}
        response = self.session.get(f"{self.host}{path}", params=query, timeout=timeout)
        if response.status_code != 200:
            raise RuntimeError(f"FanDuel API {response.status_code}: {response.text[:200]}")
        return response.json()

    def _events_from_payload(self, payload: dict[str, Any]) -> list[FanDuelEvent]:
        events = (payload.get("attachments") or {}).get("events") or {}
        results: list[FanDuelEvent] = []
        for event_id, event in events.items():
            name = str(event.get("name", "")).strip()
            if not name:
                continue
            if any(
                marker in name
                for marker in (
                    " US Open ",
                    "Wimbledon 2026",
                    "French Open 202",
                    "Australian Open 202",
                    " Outright",
                    " Winner",
                )
            ):
                continue
            home, away = split_event_players(name)
            if not away:
                continue
            results.append(
                FanDuelEvent(
                    event_id=str(event_id),
                    name=name,
                    open_date=str(event.get("openDate", "")),
                    home_player=home,
                    away_player=away,
                    is_doubles="/" in name,
                )
            )
        return results

    def list_page_events(self, custom_page_id: str) -> list[FanDuelEvent]:
        payload = self._get(
            "/api/content-managed-page",
            {"page": "CUSTOM", "customPageId": custom_page_id},
        )
        return self._events_from_payload(payload)

    def list_inplay_tennis_events(self, *, tab: str = "all") -> list[FanDuelEvent]:
        payload = self._get(
            "/api/in-play",
            {"eventTypeId": TENNIS_EVENT_TYPE_ID, "tab": tab},
        )
        return self._events_from_payload(payload)

    def list_competition_tennis_events(self, competition_id: str) -> list[FanDuelEvent]:
        payload = self._get(
            "/api/competition-page",
            {
                "page": "COMPETITION",
                "competitionId": str(competition_id),
                "eventTypeId": TENNIS_EVENT_TYPE_ID,
            },
        )
        return self._events_from_payload(payload)

    def _absorb_singles(self, merged: dict[str, FanDuelEvent], events: Iterable[FanDuelEvent]) -> None:
        for event in events:
            if event.is_doubles:
                continue
            merged[event.event_id] = event

    def _absorb_competitions_from_payload(
        self,
        merged: dict[str, FanDuelEvent],
        payload: dict[str, Any],
    ) -> None:
        self._absorb_singles(merged, self._events_from_payload(payload))
        competitions = (payload.get("attachments") or {}).get("competitions") or {}
        for comp_id in competitions:
            try:
                self._absorb_singles(merged, self.list_competition_tennis_events(str(comp_id)))
            except RuntimeError:
                continue

    def list_all_tennis_events(self) -> list[FanDuelEvent]:
        """In-play + page SPORT (toutes competitions) + pages CUSTOM."""
        merged: dict[str, FanDuelEvent] = {}

        try:
            inplay_payload = self._get(
                "/api/in-play",
                {"eventTypeId": TENNIS_EVENT_TYPE_ID, "tab": "all"},
            )
            self._absorb_competitions_from_payload(merged, inplay_payload)
        except RuntimeError:
            pass

        try:
            sport_payload = self._get(
                "/api/content-managed-page",
                {"page": "SPORT", "eventTypeId": TENNIS_EVENT_TYPE_ID},
            )
            self._absorb_competitions_from_payload(merged, sport_payload)
        except RuntimeError:
            pass

        page_ids = self.discover_tennis_page_ids(DEFAULT_TENNIS_PAGE_CANDIDATES)
        self._absorb_singles(merged, self.list_tennis_events(page_ids))

        return list(merged.values())

    def page_has_events(self, custom_page_id: str) -> bool:
        try:
            return bool(self.list_page_events(custom_page_id))
        except RuntimeError:
            return False

    def discover_tennis_page_ids(self, candidate_page_ids: tuple[str, ...] | list[str]) -> tuple[str, ...]:
        page_ids = []
        for page_id in candidate_page_ids:
            if self.page_has_events(page_id):
                page_ids.append(page_id)
        return tuple(page_ids)

    def list_tennis_events(self, page_ids: tuple[str, ...] = DEFAULT_PAGE_IDS) -> list[FanDuelEvent]:
        events: dict[str, FanDuelEvent] = {}
        for page_id in page_ids:
            for event in self.list_page_events(page_id):
                events[event.event_id] = event
        return list(events.values())

    def get_event_markets(
        self,
        event_id: str,
        tabs: tuple[str, ...] | None = None,
        *,
        timeout: float = 15.0,
    ) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for tab in tabs or EVENT_TABS:
            payload = self._get(
                "/api/event-page",
                {"eventId": event_id, "tab": tab},
                timeout=timeout,
            )
            markets = (payload.get("attachments") or {}).get("markets") or {}
            for market_id, market in markets.items():
                if market_id not in merged:
                    merged[market_id] = market
                    continue
                existing_runners = {
                    runner.get("selectionId"): runner
                    for runner in merged[market_id].get("runners", [])
                }
                for runner in market.get("runners", []):
                    selection_id = runner.get("selectionId")
                    if selection_id not in existing_runners:
                        merged[market_id].setdefault("runners", []).append(runner)
        return list(merged.values())

    def build_event_payload(
        self,
        event: FanDuelEvent,
        pause: float = 0.0,
        *,
        tabs: tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        markets = self.get_event_markets(event.event_id, tabs=tabs)
        if pause:
            time.sleep(pause)
        return {
            "event_id": event.event_id,
            "event": event.name,
            "home_player": event.home_player,
            "away_player": event.away_player,
            "is_doubles": event.is_doubles,
            "open_date": event.open_date,
            "market_count": len(markets),
            "markets": markets,
        }
