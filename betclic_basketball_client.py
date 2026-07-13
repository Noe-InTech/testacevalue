"""Client Betclic FR — basketball / WNBA."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from basketball_constants import BETCLIC_BASKETBALL_GRPC_CATEGORIES, BETCLIC_WNBA_LISTING_PATH
from betclic_client import BetclicClient

WNBA_TEAM_SLUGS: tuple[tuple[str, str], ...] = (
    ("atlanta-dream", "Atlanta Dream"),
    ("los-angeles-sparks", "Los Angeles Sparks"),
    ("minnesota-lynx", "Minnesota Lynx"),
    ("phoenix-mercury", "Phoenix Mercury"),
    ("connecticut-sun", "Connecticut Sun"),
    ("portland-fire", "Portland Fire"),
    ("toronto-tempo", "Toronto Tempo"),
    ("washington-mystics", "Washington Mystics"),
)


@dataclass(frozen=True)
class BetclicBasketballMatchLink:
    match_id: str
    url: str
    slug: str
    home_team: str
    away_team: str


class BetclicBasketballClient(BetclicClient):
    def list_wnba_matches(self) -> list[BetclicBasketballMatchLink]:
        html = self.get_page_html(BETCLIC_WNBA_LISTING_PATH)
        links: dict[str, BetclicBasketballMatchLink] = {}
        for href in re.findall(
            r'href="(/basketball-sbasketball/wnba-c\d+/[^"]+-m\d+)"',
            html,
            flags=re.I,
        ):
            if "wnba-20" in href.lower():
                continue
            match = re.search(r"-m(\d+)$", href)
            if not match:
                continue
            slug = href.rsplit("/", 1)[-1]
            home, away = self._teams_from_slug(slug)
            if not home or not away:
                continue
            match_id = match.group(1)
            links[match_id] = BetclicBasketballMatchLink(
                match_id=match_id,
                url=f"{self.base_url}{href}",
                slug=slug,
                home_team=home,
                away_team=away,
            )
        return sorted(links.values(), key=lambda item: item.url)

    @staticmethod
    def _teams_from_slug(slug: str) -> tuple[str, str]:
        body = slug.rsplit("-m", 1)[0].lower()
        found: list[tuple[int, str]] = []
        for token, name in WNBA_TEAM_SLUGS:
            index = body.find(token)
            if index >= 0:
                found.append((index, name))
        found.sort(key=lambda item: item[0])
        if len(found) >= 2:
            return found[0][1], found[1][1]
        return "", ""

    def build_event_payload(self, link: BetclicBasketballMatchLink) -> dict[str, Any]:
        payload = self.get_full_match_payload(
            link.url,
            grpc_categories=BETCLIC_BASKETBALL_GRPC_CATEGORIES,
        )
        match = payload.get("match") or {}
        contestants = match.get("contestants") or []
        home = link.home_team or (contestants[0].get("name", "") if contestants else "")
        away = link.away_team or (contestants[1].get("name", "") if len(contestants) > 1 else "")
        markets = self.extract_markets_from_match_payload(payload)
        roster = self._extract_roster_from_markets(markets, fallback=[home, away])
        return {
            "url": link.url,
            "match_id": link.match_id,
            "name": str(match.get("name", "")) or f"{home} - {away}",
            "home_team": home,
            "away_team": away,
            "start_date": match.get("matchDateUtc", ""),
            "competition": ((match.get("competition") or {}).get("name", "WNBA")),
            "roster": roster,
            "market_count": len(markets),
            "markets": [
                {"label": market.label, "outcomes": [(o.label, o.odds) for o in market.outcomes]}
                for market in markets
            ],
        }

    @staticmethod
    def _extract_roster_from_markets(markets: Any, *, fallback: list[str]) -> list[str]:
        garbage = {"joueur", "equipe", "player"}
        roster: list[str] = []
        outcome_player = re.compile(
            r"^(.+?)\s*[+-]\s*de\s*[\d.,]+",
            flags=re.I,
        )
        for market in markets:
            for outcome in market.outcomes:
                match = outcome_player.match(outcome.label.strip())
                if match:
                    name = match.group(1).strip()
                    if name.lower() not in garbage and not name.lower().endswith(" gagne &"):
                        roster.append(name)
                parsed = re.search(r"-\s*(.+?)\s*\(([\d.,]+)\)\s*$", market.label)
                if parsed:
                    name = parsed.group(1).strip()
                    if name.lower() not in garbage:
                        roster.append(name)
        cleaned = sorted({name for name in roster if name})
        return cleaned or [name for name in fallback if name]
