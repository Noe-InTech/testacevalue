"""Client Winamax FR — basketball / WNBA (séparé du client tennis)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from basketball_constants import WINAMAX_BASKETBALL_SPORT_ID
from winamax_client import WinamaxClient, WinamaxMatchLink


@dataclass(frozen=True)
class WinamaxBasketballMatchLink:
    match_id: str
    url: str
    title: str
    home_team: str
    away_team: str
    start_date: str
    competition: str
    status: str = ""


class WinamaxBasketballClient(WinamaxClient):
    def list_wnba_matches(self) -> list[WinamaxBasketballMatchLink]:
        payload = self.fetch_route(f"sport:{WINAMAX_BASKETBALL_SPORT_ID}")
        if not payload:
            return []
        matches = payload.get("matches") or {}
        links: list[WinamaxBasketballMatchLink] = []
        for match_id, match in matches.items():
            if not isinstance(match, dict):
                continue
            if int(match.get("sportId") or 0) not in (0, WINAMAX_BASKETBALL_SPORT_ID):
                continue
            parsed = self._parse_basketball_match(str(match_id), match)
            if parsed and self._looks_like_wnba(parsed):
                links.append(parsed)
        links.sort(key=lambda item: (item.start_date, item.title))
        return links

    @staticmethod
    def _looks_like_wnba(link: WinamaxBasketballMatchLink) -> bool:
        blob = f"{link.title} {link.competition}".lower()
        wnba_markers = (
            "wnba",
            "dream",
            "sparks",
            "lynx",
            "mercury",
            "aces",
            "fever",
            "sky",
            "sun",
            "liberty",
            "wings",
            "storm",
            "mystics",
        )
        return any(marker in blob for marker in wnba_markers)

    def _parse_basketball_match(
        self,
        match_id: str,
        match: dict[str, Any],
    ) -> WinamaxBasketballMatchLink | None:
        title = str(match.get("title") or match.get("name") or "").strip()
        home_team = str(match.get("competitor1Name") or "").strip()
        away_team = str(match.get("competitor2Name") or "").strip()
        if home_team and away_team:
            title = f"{home_team} - {away_team}"
        elif " - " not in title:
            return None
        else:
            home_team, away_team = [part.strip() for part in title.split(" - ", 1)]
        tournament = match.get("tournament") or {}
        competition = ""
        if isinstance(tournament, dict):
            competition = str(tournament.get("tournamentName") or tournament.get("name") or "")
        return WinamaxBasketballMatchLink(
            match_id=str(match_id),
            url=self._match_url(str(match_id)),
            title=title,
            home_team=home_team,
            away_team=away_team,
            start_date=str(match.get("matchStart") or match.get("startTime") or ""),
            competition=competition,
            status=str(match.get("status") or "").strip().upper(),
        )

    def build_event_payload(self, link: WinamaxBasketballMatchLink) -> dict[str, Any]:
        payload = self.fetch_route(f"match:{link.match_id}")
        if not payload:
            raise RuntimeError(f"Winamax payload introuvable pour match:{link.match_id}")
        markets = self.extract_markets_from_payload(payload, link.match_id)
        roster = self._extract_roster(payload, link)
        return {
            "url": link.url,
            "match_id": link.match_id,
            "name": link.title,
            "home_team": link.home_team,
            "away_team": link.away_team,
            "start_date": link.start_date,
            "competition": link.competition,
            "roster": roster,
            "market_count": len(markets),
            "markets": [
                {"label": market.label, "outcomes": [(item.label, item.odds) for item in market.outcomes]}
                for market in markets
            ],
        }

    @staticmethod
    def _extract_roster(payload: dict[str, Any], link: WinamaxBasketballMatchLink) -> list[str]:
        roster: list[str] = []
        players = payload.get("players") or {}
        for player in players.values():
            if not isinstance(player, dict):
                continue
            name = str(player.get("name") or player.get("playerName") or "").strip()
            if name:
                roster.append(name)
        if not roster:
            roster = [link.home_team, link.away_team]
        return roster

    def to_tennis_style_link(self, link: WinamaxBasketballMatchLink) -> WinamaxMatchLink:
        return WinamaxMatchLink(
            match_id=link.match_id,
            url=link.url,
            title=link.title,
            home_player=link.home_team,
            away_player=link.away_team,
            start_date=link.start_date,
            competition=link.competition,
            status=link.status,
        )
