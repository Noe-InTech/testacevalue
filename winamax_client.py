"""Client Winamax FR via Socket.IO (sport tennis)."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any

import socketio

logging.getLogger("engineio").setLevel(logging.WARNING)
logging.getLogger("socketio").setLevel(logging.WARNING)

SOCKET_URL = "https://sports-eu-west-3.winamax.fr"
SOCKET_PATH = "/uof-sports-server/socket.io/"
TENNIS_SPORT_ID = 5
DEFAULT_ORIGIN = "https://www.winamax.fr"
BASE_URL = "https://www.winamax.fr"


@dataclass(frozen=True)
class WinamaxMatchLink:
    match_id: str
    url: str
    title: str
    home_player: str
    away_player: str
    start_date: str
    competition: str


@dataclass(frozen=True)
class WinamaxOutcome:
    label: str
    odds: float | None


@dataclass(frozen=True)
class WinamaxMarket:
    label: str
    outcomes: tuple[WinamaxOutcome, ...]


class WinamaxClient:
    def __init__(
        self,
        *,
        socket_url: str = SOCKET_URL,
        socket_path: str = SOCKET_PATH,
        base_url: str = BASE_URL,
        fetch_timeout: float = 8.0,
    ):
        self.socket_url = socket_url
        self.socket_path = socket_path
        self.base_url = base_url.rstrip("/")
        self.fetch_timeout = fetch_timeout

    @staticmethod
    def _parse_line(special_bet_value: str | None) -> str:
        if not special_bet_value:
            return ""
        match = re.search(r"total=([\d.,]+)", special_bet_value)
        if not match:
            return ""
        value = match.group(1).replace(",", ".")
        try:
            number = float(value)
        except ValueError:
            return ""
        if number.is_integer():
            return str(int(number))
        return str(number)

    @staticmethod
    def _lookup(mapping: dict[Any, Any], key: Any) -> Any:
        if key in mapping:
            return mapping[key]
        return mapping.get(str(key))

    def fetch_routes(self, routes: list[str], timeout: float | None = None) -> dict[str, dict[str, Any] | None]:
        if not routes:
            return {}
        wait_time = self.fetch_timeout if timeout is None else timeout
        request_ids = {route: str(uuid.uuid4()) for route in routes}
        results: dict[str, dict[str, Any] | None] = {route: None for route in routes}

        sio = socketio.Client(logger=False, engineio_logger=False)

        @sio.on("m")
        def on_message(data: dict[str, Any]) -> None:
            request_id = data.get("requestId")
            for route, route_request_id in request_ids.items():
                if route_request_id == request_id:
                    results[route] = data

        sio.connect(
            self.socket_url,
            transports=["websocket"],
            socketio_path=self.socket_path,
            headers={"Origin": DEFAULT_ORIGIN},
        )
        for route, request_id in request_ids.items():
            sio.emit("m", {"route": route, "requestId": request_id})
        sio.sleep(wait_time)
        sio.disconnect()
        return results

    def fetch_route(self, route: str, timeout: float | None = None) -> dict[str, Any] | None:
        return self.fetch_routes([route], timeout=timeout).get(route)

    def _match_url(self, match_id: str) -> str:
        return f"{self.base_url}/paris-sportifs/match/{match_id}"

    @staticmethod
    def _is_doubles_title(title: str) -> bool:
        lower = title.lower()
        if "/" in title:
            return True
        if " double" in lower or "doubles" in lower:
            return True
        return False

    @staticmethod
    def _is_future_or_outright(title: str) -> bool:
        lower = title.lower()
        markers = (
            "wimbledon",
            "roland garros",
            "us open",
            "open d'australie",
            "australian open",
            "atp -",
            "wta -",
            "vainqueur",
        )
        return any(marker in lower for marker in markers)

    def _parse_match(self, match_id: str, match: dict[str, Any]) -> WinamaxMatchLink | None:
        title = str(match.get("title") or match.get("name") or "").strip()
        home_player = str(match.get("competitor1Name") or "").strip()
        away_player = str(match.get("competitor2Name") or "").strip()
        if home_player and away_player:
            title = f"{home_player} - {away_player}"
        elif " - " not in title:
            return None
        else:
            home_player, away_player = [part.strip() for part in title.split(" - ", 1)]
        if self._is_doubles_title(title) or self._is_future_or_outright(title):
            return None
        if not home_player or not away_player:
            return None
        tournament = match.get("tournament") or {}
        if isinstance(tournament, dict):
            competition = str(tournament.get("tournamentName") or tournament.get("name") or "")
        else:
            competition = ""
        return WinamaxMatchLink(
            match_id=str(match_id),
            url=self._match_url(str(match_id)),
            title=title,
            home_player=home_player,
            away_player=away_player,
            start_date=str(match.get("matchStart") or match.get("startTime") or ""),
            competition=competition,
        )

    def list_singles_tennis_matches(self) -> list[WinamaxMatchLink]:
        payload = self.fetch_route(f"sport:{TENNIS_SPORT_ID}")
        if not payload:
            return []
        matches = payload.get("matches") or {}
        links: list[WinamaxMatchLink] = []
        for match_id, match in matches.items():
            if not isinstance(match, dict):
                continue
            if int(match.get("sportId") or 0) not in (0, TENNIS_SPORT_ID):
                continue
            parsed = self._parse_match(str(match_id), match)
            if parsed:
                links.append(parsed)
        links.sort(key=lambda item: (item.start_date, item.title))
        return links

    def extract_markets_from_payload(
        self,
        payload: dict[str, Any],
        match_id: str,
    ) -> list[WinamaxMarket]:
        bets = payload.get("bets") or {}
        outcomes = payload.get("outcomes") or {}
        odds = payload.get("odds") or {}
        markets: list[WinamaxMarket] = []

        for bet in bets.values():
            if not isinstance(bet, dict):
                continue
            if str(bet.get("matchId")) != str(match_id):
                continue
            if bet.get("available") is False:
                continue
            title = str(bet.get("betTitle") or bet.get("betTypeName") or "").strip()
            if not title:
                continue
            line = self._parse_line(str(bet.get("specialBetValue") or ""))
            label = f"{title} ({line})" if line else title
            parsed_outcomes: list[WinamaxOutcome] = []
            for outcome_id in bet.get("outcomes") or []:
                outcome = self._lookup(outcomes, outcome_id)
                if not isinstance(outcome, dict):
                    continue
                outcome_label = str(
                    outcome.get("label")
                    or outcome.get("name")
                    or outcome.get("outcomeName")
                    or ""
                ).strip()
                if not outcome_label:
                    continue
                raw_odds = self._lookup(odds, outcome_id)
                try:
                    parsed_odds = float(raw_odds) if raw_odds is not None else None
                except (TypeError, ValueError):
                    parsed_odds = None
                parsed_outcomes.append(WinamaxOutcome(label=outcome_label, odds=parsed_odds))
            if parsed_outcomes:
                markets.append(WinamaxMarket(label=label, outcomes=tuple(parsed_outcomes)))
        return markets

    def get_event_markets(self, match_id: str) -> list[WinamaxMarket]:
        payload = self.fetch_route(f"match:{match_id}")
        if not payload:
            return []
        return self.extract_markets_from_payload(payload, match_id)

    def build_event_payload(self, link: WinamaxMatchLink) -> dict[str, Any]:
        payload = self.fetch_route(f"match:{link.match_id}")
        if not payload:
            raise RuntimeError(f"Winamax payload introuvable pour match:{link.match_id}")
        markets = self.extract_markets_from_payload(payload, link.match_id)
        return {
            "url": link.url,
            "match_id": link.match_id,
            "name": link.title,
            "home_player": link.home_player,
            "away_player": link.away_player,
            "start_date": link.start_date,
            "competition": link.competition,
            "market_count": len(markets),
            "markets": [
                {"label": market.label, "outcomes": [(item.label, item.odds) for item in market.outcomes]}
                for market in markets
            ],
        }

    def build_event_payloads(self, links: list[WinamaxMatchLink]) -> list[dict[str, Any]]:
        if not links:
            return []
        routes = [f"match:{link.match_id}" for link in links]
        payloads = self.fetch_routes(routes)
        events: list[dict[str, Any]] = []
        for link in links:
            payload = payloads.get(f"match:{link.match_id}")
            if not payload:
                continue
            markets = self.extract_markets_from_payload(payload, link.match_id)
            events.append(
                {
                    "url": link.url,
                    "match_id": link.match_id,
                    "name": link.title,
                    "home_player": link.home_player,
                    "away_player": link.away_player,
                    "start_date": link.start_date,
                    "competition": link.competition,
                    "market_count": len(markets),
                    "markets": [
                        {
                            "label": market.label,
                            "outcomes": [(item.label, item.odds) for item in market.outcomes],
                        }
                        for market in markets
                    ],
                }
            )
        return events
