from dataclasses import dataclass
from typing import Any

import requests

BASE_URL = "https://api.the-odds-api.com/v4"


@dataclass
class QuotaInfo:
    remaining: int | None
    used: int | None
    last_cost: int | None


class OddsApiClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.last_quota = QuotaInfo(None, None, None)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        params = dict(params or {})
        params["apiKey"] = self.api_key

        response = self.session.get(f"{BASE_URL}{path}", params=params, timeout=30)
        self._update_quota(response.headers)

        if response.status_code != 200:
            raise RuntimeError(
                f"API error {response.status_code}: {response.text[:300]}"
            )

        return response.json()

    def _update_quota(self, headers: dict[str, str]) -> None:
        self.last_quota = QuotaInfo(
            remaining=_parse_int(headers.get("x-requests-remaining")),
            used=_parse_int(headers.get("x-requests-used")),
            last_cost=_parse_int(headers.get("x-requests-last")),
        )

    def get_sports(self, all_sports: bool = False) -> list[dict]:
        params = {"all": "true"} if all_sports else {}
        return self._get("/sports", params)

    def get_events(self, sport: str) -> list[dict]:
        return self._get(f"/sports/{sport}/events")

    def get_event_markets(
        self,
        sport: str,
        event_id: str,
        bookmakers: list[str],
    ) -> dict:
        return self._get(
            f"/sports/{sport}/events/{event_id}/markets",
            {"bookmakers": ",".join(bookmakers)},
        )

    def get_event_odds(
        self,
        sport: str,
        event_id: str,
        bookmakers: list[str],
        markets: list[str],
        odds_format: str = "decimal",
    ) -> dict:
        return self._get(
            f"/sports/{sport}/events/{event_id}/odds",
            {
                "bookmakers": ",".join(bookmakers),
                "markets": ",".join(markets),
                "oddsFormat": odds_format,
            },
        )

def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
