"""Client Winamax FR — baseball / MLB / KBO / NPB."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from baseball_constants import (
    WINAMAX_BASEBALL_SPORT_ID,
    WINAMAX_KBO_TOURNAMENT_ID,
    WINAMAX_MLB_TOURNAMENT_ID,
    WINAMAX_NPB_TOURNAMENT_ID,
)
from baseball_listings import competition_from_blob
from winamax_client import WinamaxClient


@dataclass(frozen=True)
class WinamaxBaseballMatchLink:
    match_id: str
    url: str
    title: str
    home_team: str
    away_team: str
    start_date: str
    competition: str
    status: str = ""


class WinamaxBaseballClient(WinamaxClient):
    def list_mlb_matches(self) -> list[WinamaxBaseballMatchLink]:
        return self._list_by_tournament(WINAMAX_MLB_TOURNAMENT_ID, "MLB")

    def list_kbo_matches(self) -> list[WinamaxBaseballMatchLink]:
        return self._list_by_tournament(WINAMAX_KBO_TOURNAMENT_ID, "KBO")

    def list_npb_matches(self) -> list[WinamaxBaseballMatchLink]:
        return self._list_by_tournament(WINAMAX_NPB_TOURNAMENT_ID, "NPB")

    def list_baseball_matches(self) -> list[WinamaxBaseballMatchLink]:
        merged: dict[str, WinamaxBaseballMatchLink] = {}
        for link in [
            *self.list_mlb_matches(),
            *self.list_kbo_matches(),
            *self.list_npb_matches(),
        ]:
            merged[link.match_id] = link
        return sorted(merged.values(), key=lambda item: (item.competition, item.start_date, item.title))

    def _list_by_tournament(
        self,
        tournament_id: int,
        competition: str,
    ) -> list[WinamaxBaseballMatchLink]:
        payload = self.fetch_route(f"sport:{WINAMAX_BASEBALL_SPORT_ID}")
        if not payload:
            return []
        matches = payload.get("matches") or {}
        links: list[WinamaxBaseballMatchLink] = []
        for match_id, match in matches.items():
            if not isinstance(match, dict):
                continue
            if int(match.get("sportId") or 0) not in (0, WINAMAX_BASEBALL_SPORT_ID):
                continue
            if int(match.get("tournamentId") or 0) != int(tournament_id):
                continue
            parsed = self._parse_match(str(match_id), match, competition=competition)
            if parsed and parsed.status in {"", "PREMATCH", "LIVE"}:
                # Skip season-long outright rows
                if "2026" in parsed.title and " - " not in parsed.title.replace("St. ", "St "):
                    if parsed.title.strip().endswith("2026"):
                        continue
                links.append(parsed)
        links.sort(key=lambda item: (item.start_date, item.title))
        return links

    def _parse_match(
        self,
        match_id: str,
        match: dict[str, Any],
        *,
        competition: str,
    ) -> WinamaxBaseballMatchLink | None:
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
        return WinamaxBaseballMatchLink(
            match_id=str(match_id),
            url=self._match_url(str(match_id)),
            title=title,
            home_team=home,
            away_team=away,
            start_date=str(match.get("matchStart") or match.get("startTime") or ""),
            competition=competition or competition_from_blob(title),
            status=str(match.get("status") or "").strip().upper(),
        )

    def build_event_payload(self, link: WinamaxBaseballMatchLink) -> dict[str, Any]:
        payload = self.fetch_route(f"match:{link.match_id}")
        if not payload:
            raise RuntimeError(f"Winamax payload introuvable pour match:{link.match_id}")
        markets = self.extract_markets_from_payload(payload, link.match_id)
        roster = self._extract_roster(payload)
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
            "markets": self.markets_to_payload(markets),
        }

    @staticmethod
    def _extract_roster(payload: dict[str, Any]) -> list[str]:
        roster: list[str] = []
        players = payload.get("players") or {}
        for player in players.values():
            if not isinstance(player, dict):
                continue
            name = str(player.get("name") or player.get("playerName") or "").strip()
            if name:
                roster.append(name)
        return roster
