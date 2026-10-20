"""Client Betclic FR — basketball / WNBA."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from basketball_constants import (
    BETCLIC_NBA_COMPETITION_PREFIX,
    BETCLIC_NBA_LISTING_PATH,
    BETCLIC_WNBA_LISTING_PATH,
)
from basketball_listings import is_basketball_outright_slug
from betclic_client import BetclicClient

# Tokens les plus longs en premier (évite « heat » dans « something-heat »).
NBA_TEAM_SLUGS: tuple[tuple[str, str], ...] = tuple(
    sorted(
        (
            ("los-angeles-clippers", "Los Angeles Clippers"),
            ("los-angeles-lakers", "Los Angeles Lakers"),
            ("golden-state-warriors", "Golden State Warriors"),
            ("oklahoma-city-thunder", "Oklahoma City Thunder"),
            ("san-antonio-spurs", "San Antonio Spurs"),
            ("new-orleans-pelicans", "New Orleans Pelicans"),
            ("portland-trail-blazers", "Portland Trail Blazers"),
            ("minnesota-timberwolves", "Minnesota Timberwolves"),
            ("philadelphia-76ers", "Philadelphia 76ers"),
            ("sacramento-kings", "Sacramento Kings"),
            ("detroit-pistons", "Detroit Pistons"),
            ("boston-celtics", "Boston Celtics"),
            ("brooklyn-nets", "Brooklyn Nets"),
            ("charlotte-hornets", "Charlotte Hornets"),
            ("chicago-bulls", "Chicago Bulls"),
            ("cleveland-cavaliers", "Cleveland Cavaliers"),
            ("dallas-mavericks", "Dallas Mavericks"),
            ("denver-nuggets", "Denver Nuggets"),
            ("houston-rockets", "Houston Rockets"),
            ("indiana-pacers", "Indiana Pacers"),
            ("memphis-grizzlies", "Memphis Grizzlies"),
            ("miami-heat", "Miami Heat"),
            ("milwaukee-bucks", "Milwaukee Bucks"),
            ("new-york-knicks", "New York Knicks"),
            ("orlando-magic", "Orlando Magic"),
            ("phoenix-suns", "Phoenix Suns"),
            ("toronto-raptors", "Toronto Raptors"),
            ("utah-jazz", "Utah Jazz"),
            ("washington-wizards", "Washington Wizards"),
            ("atlanta-hawks", "Atlanta Hawks"),
        ),
        key=lambda item: len(item[0]),
        reverse=True,
    )
)

WNBA_TEAM_SLUGS: tuple[tuple[str, str], ...] = tuple(
    sorted(
        (
            ("golden-state-valkyries", "Golden State Valkyries"),
            ("los-angeles-sparks", "Los Angeles Sparks"),
            ("las-vegas-aces", "Las Vegas Aces"),
            ("new-york-liberty", "New York Liberty"),
            ("connecticut-sun", "Connecticut Sun"),
            ("washington-mystics", "Washington Mystics"),
            ("minnesota-lynx", "Minnesota Lynx"),
            ("phoenix-mercury", "Phoenix Mercury"),
            ("atlanta-dream", "Atlanta Dream"),
            ("chicago-sky", "Chicago Sky"),
            ("dallas-wings", "Dallas Wings"),
            ("indiana-fever", "Indiana Fever"),
            ("portland-fire", "Portland Fire"),
            ("seattle-storm", "Seattle Storm"),
            ("toronto-tempo", "Toronto Tempo"),
        ),
        key=lambda item: len(item[0]),
        reverse=True,
    )
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
        pattern = r'href="(/basketball-sbasketball/wnba-c\d+/[^"]+-m\d+)"'
        links: dict[str, BetclicBasketballMatchLink] = {}
        html = self.get_page_html(BETCLIC_WNBA_LISTING_PATH)
        hub_paths = sorted(
            {
                f"/basketball-sbasketball/{token}"
                for token in re.findall(r"/basketball-sbasketball/(wnba-c\d+)", html, flags=re.I)
            }
        )
        pages = [BETCLIC_WNBA_LISTING_PATH, *hub_paths]
        for path in pages:
            page_html = html if path == BETCLIC_WNBA_LISTING_PATH else self.get_page_html(path)
            self._collect_basketball_hrefs(
                page_html,
                pattern,
                links,
                team_slugs=WNBA_TEAM_SLUGS,
                skip_href=lambda href: "wnba-20" in href.lower(),
            )
        return sorted(links.values(), key=lambda item: item.url)

    def list_nba_matches(self) -> list[BetclicBasketballMatchLink]:
        pattern = (
            rf'href="(/basketball-sbasketball/{re.escape(BETCLIC_NBA_COMPETITION_PREFIX)}/[^"]+-m\d+)"'
        )
        links: dict[str, BetclicBasketballMatchLink] = {}
        hub = f"/basketball-sbasketball/{BETCLIC_NBA_COMPETITION_PREFIX}"
        for path in (BETCLIC_NBA_LISTING_PATH, hub):
            html = self.get_page_html(path)
            self._collect_basketball_hrefs(
                html,
                pattern,
                links,
                team_slugs=NBA_TEAM_SLUGS,
                skip_href=lambda href: "nba-cup" in href.lower(),
                skip_slug=is_basketball_outright_slug,
            )
        return sorted(links.values(), key=lambda item: item.url)

    def _collect_basketball_hrefs(
        self,
        html: str,
        pattern: str,
        links: dict[str, BetclicBasketballMatchLink],
        *,
        team_slugs: tuple[tuple[str, str], ...],
        skip_href: Any = None,
        skip_slug: Any = None,
    ) -> None:
        for href in re.findall(pattern, html, flags=re.I):
            if skip_href and skip_href(href):
                continue
            match = re.search(r"-m(\d+)$", href)
            if not match:
                continue
            slug = href.rsplit("/", 1)[-1]
            if skip_slug and skip_slug(slug):
                continue
            home, away = self._teams_from_token_slug(slug, team_slugs)
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

    @staticmethod
    def _teams_from_token_slug(
        slug: str,
        team_slugs: tuple[tuple[str, str], ...],
    ) -> tuple[str, str]:
        body = re.sub(r"-m\d+$", "", slug).lower()
        for sep in ("-vs-", "-v-"):
            if sep in body:
                left, right = body.split(sep, 1)
                return (
                    BetclicBasketballClient._name_from_slug_fragment(left, team_slugs),
                    BetclicBasketballClient._name_from_slug_fragment(right, team_slugs),
                )

        found: list[tuple[int, int, str]] = []
        used: set[int] = set()
        for token, name in team_slugs:
            start = 0
            while True:
                index = body.find(token, start)
                if index < 0:
                    break
                end = index + len(token)
                if any(pos in used for pos in range(index, end)):
                    start = index + 1
                    continue
                left_ok = index == 0 or body[index - 1] == "-"
                right_ok = end == len(body) or body[end] == "-"
                if left_ok and right_ok:
                    found.append((index, end, name))
                    used.update(range(index, end))
                    break
                start = index + 1
        found.sort(key=lambda item: item[0])
        if len(found) >= 2:
            return found[0][2], found[1][2]
        return "", ""

    @staticmethod
    def _name_from_slug_fragment(
        value: str,
        team_slugs: tuple[tuple[str, str], ...],
    ) -> str:
        token = value.strip("-").lower()
        for slug, name in team_slugs:
            if slug == token:
                return name
        return " ".join(part.capitalize() for part in token.split("-"))

    @staticmethod
    def _teams_from_nba_slug(slug: str) -> tuple[str, str]:
        return BetclicBasketballClient._teams_from_token_slug(slug, NBA_TEAM_SLUGS)

    @staticmethod
    def _teams_from_slug(slug: str) -> tuple[str, str]:
        return BetclicBasketballClient._teams_from_token_slug(slug, WNBA_TEAM_SLUGS)

    def build_event_payload(self, link: BetclicBasketballMatchLink) -> dict[str, Any]:
        # SSR suffit pour les props joueur (+/-, paliers, PRA) ; le gRPC complet
        # peut prendre plusieurs minutes par match et faire expirer le compare NBA (600s).
        payload = self.get_match_payload(link.url)
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
            "markets": self.markets_to_payload(markets),
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
