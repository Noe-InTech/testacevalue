"""Client Unibet FR — football (buteurs / props joueur)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from unibet_client import UnibetClient

UNIBET_SOCCER_HUB_PATHS: tuple[str, ...] = (
    "/sport/football",
    "/paris-football",
)


@dataclass(frozen=True)
class UnibetSoccerEvent:
    event_id: str
    name: str
    home_team: str
    away_team: str
    url: str


class UnibetSoccerClient(UnibetClient):
    def list_soccer_events(self) -> list[UnibetSoccerEvent]:
        events: dict[str, UnibetSoccerEvent] = {}
        for path in UNIBET_SOCCER_HUB_PATHS:
            try:
                html = self.get_tennis_listing_html(path)
            except Exception:
                continue
            for match in re.finditer(
                r'href="(/paris-football/[^"]+/\d+/[^"#?]+)"',
                html,
                flags=re.I,
            ):
                path_url = match.group(1)
                parts = path_url.strip("/").split("/")
                if len(parts) < 4:
                    continue
                event_id = parts[-2]
                slug = parts[-1]
                home, away = self._teams_from_slug(slug)
                if not home or not away:
                    continue
                key = f"{home}|{away}".lower()
                url = f"{self.base_url}{path_url}"
                events[key] = UnibetSoccerEvent(
                    event_id=str(event_id),
                    name=f"{home} - {away}",
                    home_team=home,
                    away_team=away,
                    url=url,
                )
        return sorted(events.values(), key=lambda item: item.name)

    @staticmethod
    def _teams_from_slug(slug: str) -> tuple[str, str]:
        body = slug
        for sep in ("-vs-", "-v-"):
            if sep in body:
                left, right = body.split(sep, 1)
                return left.replace("-", " ").title(), right.replace("-", " ").title()
        tokens = body.split("-")
        if len(tokens) < 2:
            return "", ""
        mid = len(tokens) // 2
        home = " ".join(tokens[:mid]).title()
        away = " ".join(tokens[mid:]).title()
        return home, away

    def build_soccer_event_payload(self, event_url: str) -> dict[str, Any]:
        html = self.get_event_html(event_url)
        markets = self.extract_all_event_markets_from_html(html)
        return {
            "url": event_url,
            "markets": self.markets_to_payload(markets),
        }
