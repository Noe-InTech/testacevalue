"""Client Betclic FR — football / props joueur (SSR)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from betclic_client import BetclicClient
from soccer_constants import BETCLIC_SOCCER_LISTING_PATHS


@dataclass(frozen=True)
class BetclicSoccerMatchLink:
    match_id: str
    url: str
    slug: str
    home_team: str
    away_team: str
    competition: str = ""


def _title_from_slug_part(part: str) -> str:
    text = part.replace("-", " ").strip()
    return " ".join(p.capitalize() for p in text.split() if p)


class BetclicSoccerClient(BetclicClient):
    def list_soccer_matches(
        self,
        listing_paths: tuple[str, ...] | None = None,
    ) -> list[BetclicSoccerMatchLink]:
        paths = listing_paths or BETCLIC_SOCCER_LISTING_PATHS
        links: dict[str, BetclicSoccerMatchLink] = {}
        for path in paths:
            try:
                html = self.get_page_html(path)
            except Exception:
                continue
            for href in re.findall(
                r'href="(/football-sfootball/[^"]+-m\d+)"',
                html,
                flags=re.I,
            ):
                if "esoccer" in href.lower() or "e-soccer" in href.lower():
                    continue
                match = re.search(r"-m(\d+)$", href)
                if not match:
                    continue
                slug = href.rsplit("/", 1)[-1]
                home, away = self._teams_from_slug(slug)
                if not home or not away:
                    continue
                competition = ""
                parts = href.strip("/").split("/")
                if len(parts) >= 2:
                    competition = parts[1]
                match_id = match.group(1)
                links[match_id] = BetclicSoccerMatchLink(
                    match_id=match_id,
                    url=f"{self.base_url}{href}",
                    slug=slug,
                    home_team=home,
                    away_team=away,
                    competition=competition,
                )
        return sorted(links.values(), key=lambda item: item.url)

    @staticmethod
    def _teams_from_slug(slug: str) -> tuple[str, str]:
        body = re.sub(r"-m\d+$", "", slug)
        # betclic: home-away without vs
        # e.g. valerenga-ham-kam, marseille-strasbourg
        # Prefer split on known patterns; fallback: last 2 tokens heuristic is weak.
        # Many slugs are team1-team2 with multi-word teams — use page contestants when possible.
        # For listing we approximate by splitting mid if even token count else last hyphen group.
        tokens = body.split("-")
        if len(tokens) < 2:
            return "", ""
        # Common: two equal halves
        mid = len(tokens) // 2
        home = _title_from_slug_part("-".join(tokens[:mid]))
        away = _title_from_slug_part("-".join(tokens[mid:]))
        return home, away

    def build_soccer_event_payload(self, match_url: str) -> dict[str, Any]:
        # SSR only — avoid full gRPC (lent / hang foot).
        payload = self.get_match_payload(match_url)
        match = payload.get("match") or {}
        contestants = match.get("contestants") or []
        home = contestants[0].get("name", "") if len(contestants) > 0 else ""
        away = contestants[1].get("name", "") if len(contestants) > 1 else ""
        markets = self.extract_markets_from_match_payload(payload)
        return {
            "url": match_url,
            "match_id": str(match.get("matchId", "")),
            "name": str(match.get("name", "")),
            "home_team": home,
            "away_team": away,
            "start_date": match.get("matchDateUtc", ""),
            "competition": ((match.get("competition") or {}).get("name", "")),
            "markets": [
                {"label": market.label, "outcomes": [(o.label, o.odds) for o in market.outcomes]}
                for market in markets
            ],
        }
