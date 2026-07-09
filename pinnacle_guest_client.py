"""Client pour l'API invitée publique utilisée par le front Pinnacle."""

from dataclasses import dataclass
from typing import Any

import requests

BASE_URL = "https://guest.api.arcadia.pinnacle.com/0.1"
DEFAULT_GUEST_API_KEY = "CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R"
SOCCER_SPORT_ID = 29


@dataclass(frozen=True)
class PinnacleLeague:
    id: int
    group: str
    name: str
    matchup_count: int


class PinnacleGuestClient:
    def __init__(self, api_key: str = DEFAULT_GUEST_API_KEY):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": api_key})

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self.session.get(f"{BASE_URL}{path}", params=params, timeout=30)
        if response.status_code != 200:
            raise RuntimeError(
                f"Pinnacle guest API error {response.status_code}: {response.text[:300]}"
            )
        return response.json()

    def get_sports(self) -> list[dict[str, Any]]:
        return self._get("/sports")

    def get_leagues(self, sport_id: int = SOCCER_SPORT_ID) -> list[dict[str, Any]]:
        return self._get(f"/sports/{sport_id}/leagues")

    def list_active_soccer_leagues(self) -> list[PinnacleLeague]:
        leagues = []
        for league in self.get_leagues(SOCCER_SPORT_ID):
            matchup_count = int(league.get("matchupCount", 0) or 0)
            if matchup_count <= 0:
                continue
            leagues.append(
                PinnacleLeague(
                    id=int(league["id"]),
                    group=str(league.get("group", "")),
                    name=str(league.get("name", "")),
                    matchup_count=matchup_count,
                )
            )
        return leagues

    def find_world_cup_league(self) -> PinnacleLeague:
        leagues = self.get_leagues(SOCCER_SPORT_ID)
        for league in leagues:
            text = f"{league.get('group', '')} {league.get('name', '')}".lower()
            if "world cup" in text or "fifa" in text:
                return PinnacleLeague(
                    id=int(league["id"]),
                    group=str(league.get("group", "")),
                    name=str(league.get("name", "")),
                    matchup_count=int(league.get("matchupCount", 0)),
                )
        raise RuntimeError("Ligue Coupe du monde introuvable sur Pinnacle")

    def get_league_matchups(self, league_id: int) -> list[dict[str, Any]]:
        return self._get(f"/leagues/{league_id}/matchups")

    def get_league_markets(self, league_id: int) -> list[dict[str, Any]]:
        return self._get(f"/leagues/{league_id}/markets/straight")

    def get_related_matchups(self, matchup_id: int) -> list[dict[str, Any]]:
        return self._get(f"/matchups/{matchup_id}/related")

    def get_related_markets(self, matchup_id: int) -> list[dict[str, Any]]:
        return self._get(f"/matchups/{matchup_id}/markets/related/straight")
