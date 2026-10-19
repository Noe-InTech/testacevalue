"""Client Winamax FR — football (toutes compétitions listées)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from soccer_constants import WINAMAX_FOOTBALL_SPORT_ID
from winamax_client import WinamaxClient


@dataclass(frozen=True)
class WinamaxSoccerMatchLink:
    match_id: str
    url: str
    title: str
    home_team: str
    away_team: str
    start_date: str
    competition: str
    tournament_id: str = ""
    status: str = ""


class WinamaxSoccerClient(WinamaxClient):
    def list_soccer_matches(self) -> list[WinamaxSoccerMatchLink]:
        payload = self.fetch_route(f"sport:{WINAMAX_FOOTBALL_SPORT_ID}")
        if not payload:
            return []
        matches = payload.get("matches") or {}
        links: list[WinamaxSoccerMatchLink] = []
        for match_id, match in matches.items():
            if not isinstance(match, dict):
                continue
            sport_id = int(match.get("sportId") or 0)
            if sport_id not in (0, WINAMAX_FOOTBALL_SPORT_ID):
                continue
            parsed = self._parse_match(str(match_id), match)
            if parsed and parsed.status in {"", "PREMATCH", "LIVE"}:
                links.append(parsed)
        links.sort(key=lambda item: (item.start_date, item.title))
        return links

    def _parse_match(self, match_id: str, match: dict[str, Any]) -> WinamaxSoccerMatchLink | None:
        title = str(match.get("title") or "").strip()
        home = str(match.get("competitor1Name") or "").strip()
        away = str(match.get("competitor2Name") or "").strip()
        if not home or not away:
            if " - " in title:
                home, away = [part.strip() for part in title.split(" - ", 1)]
            else:
                return None
        if not title:
            title = f"{home} - {away}"
        tournament = match.get("tournament") if isinstance(match.get("tournament"), dict) else {}
        competition = str(
            tournament.get("tournamentName")
            or tournament.get("name")
            or match.get("tournamentName")
            or ""
        ).strip()
        return WinamaxSoccerMatchLink(
            match_id=str(match_id),
            url=self._match_url(str(match_id)),
            title=title,
            home_team=home,
            away_team=away,
            start_date=str(match.get("matchStart") or match.get("startTime") or ""),
            competition=competition,
            tournament_id=str(match.get("tournamentId") or ""),
            status=str(match.get("status") or "").strip().upper(),
        )

    def build_soccer_event_payload(self, link: WinamaxSoccerMatchLink) -> dict[str, Any]:
        payload = self.fetch_route(f"match:{link.match_id}")
        if not payload:
            raise RuntimeError(f"Winamax payload introuvable pour match:{link.match_id}")
        markets = self.extract_markets_from_payload(payload, link.match_id)
        return {
            "url": link.url,
            "match_id": link.match_id,
            "name": link.title,
            "home_team": link.home_team,
            "away_team": link.away_team,
            "start_date": link.start_date,
            "competition": link.competition,
            "markets": self.markets_to_payload(markets),
        }
