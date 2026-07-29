"""Client Unibet FR — baseball / MLB / KBO."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from baseball_constants import UNIBET_BASEBALL_LISTING_PATH, UNIBET_KBO_LISTING_PATH, UNIBET_MLB_LISTING_PATH
from baseball_listings import competition_from_blob, is_baseball_outright_name
from unibet_client import UnibetClient, UnibetMarket


@dataclass(frozen=True)
class UnibetBaseballEvent:
    event_id: str
    name: str
    home_team: str
    away_team: str
    url: str
    competition: str = "MLB"
    start_date: str = ""


class UnibetBaseballClient(UnibetClient):
    def list_mlb_events(self) -> list[UnibetBaseballEvent]:
        events: dict[str, UnibetBaseballEvent] = {}
        for page in (UNIBET_BASEBALL_LISTING_PATH, UNIBET_MLB_LISTING_PATH):
            html = self.get_tennis_listing_html(page)
            self._ingest_paths(
                html,
                events,
                pattern=r'href="(/paris-baseball/mlb/mlb/\d+/[^"#?]+)"',
                competition="MLB",
            )
        return sorted(events.values(), key=lambda item: item.name)

    def list_kbo_events(self) -> list[UnibetBaseballEvent]:
        events: dict[str, UnibetBaseballEvent] = {}
        try:
            html = self.get_tennis_listing_html(UNIBET_KBO_LISTING_PATH)
        except Exception:
            return []
        # Prematch links
        self._ingest_paths(
            html,
            events,
            pattern=r'href="(/paris-baseball/coree-du-sud/kbo/\d+/[^"#?]+)"',
            competition="KBO",
        )
        # Live fallback links embed event ids + slugs
        for match in re.finditer(
            r'href="(/paris-en-direct/(\d+)/([a-z0-9\-]+))"',
            html,
            flags=re.I,
        ):
            path, event_id, slug = match.group(1), match.group(2), match.group(3)
            if is_baseball_outright_name(slug):
                continue
            home, away = self._teams_from_slug(slug)
            if not home or not away:
                continue
            key = f"{home}|{away}".lower()
            url = f"{self.base_url}{path}"
            existing = events.get(key)
            if existing is None:
                events[key] = UnibetBaseballEvent(
                    event_id=str(event_id),
                    name=f"{home} - {away}",
                    home_team=home,
                    away_team=away,
                    url=url,
                    competition="KBO",
                )
        return sorted(events.values(), key=lambda item: item.name)

    def list_baseball_events(self) -> list[UnibetBaseballEvent]:
        merged: dict[str, UnibetBaseballEvent] = {}
        for event in [*self.list_mlb_events(), *self.list_kbo_events()]:
            key = f"{event.home_team}|{event.away_team}".lower()
            merged[key] = event
        return sorted(merged.values(), key=lambda item: (item.competition, item.name))

    def _ingest_paths(
        self,
        html: str,
        events: dict[str, UnibetBaseballEvent],
        *,
        pattern: str,
        competition: str,
    ) -> None:
        for match in re.finditer(pattern, html, flags=re.I):
            path = match.group(1).rstrip("/")
            slug = path.rsplit("/", 1)[-1]
            if is_baseball_outright_name(slug):
                continue
            event_id = path.split("/")[-2]
            home, away = self._teams_from_slug(slug)
            if not home or not away:
                continue
            name = f"{home} - {away}"
            key = f"{home}|{away}".lower()
            url = f"{self.base_url}{path}"
            existing = events.get(key)
            if existing is None or len(url) > len(existing.url):
                events[key] = UnibetBaseballEvent(
                    event_id=str(event_id),
                    name=name,
                    home_team=home,
                    away_team=away,
                    url=url,
                    competition=competition or competition_from_blob(path, name),
                )

    @staticmethod
    def _teams_from_slug(slug: str) -> tuple[str, str]:
        aliases = {
            "ari-dbacks": "Arizona Diamondbacks",
            "atl-braves": "Atlanta Braves",
            "bal-orioles": "Baltimore Orioles",
            "bos-red-sox": "Boston Red Sox",
            "chi-cubs": "Chicago Cubs",
            "chi-wh-sox": "Chicago White Sox",
            "cin-reds": "Cincinnati Reds",
            "cle-guardians": "Cleveland Guardians",
            "col-rockies": "Colorado Rockies",
            "det-tigers": "Detroit Tigers",
            "hou-astros": "Houston Astros",
            "kc-royals": "Kansas City Royals",
            "la-angels": "Los Angeles Angels",
            "la-dodgers": "Los Angeles Dodgers",
            "mia-marlins": "Miami Marlins",
            "mil-brewers": "Milwaukee Brewers",
            "min-twins": "Minnesota Twins",
            "ny-mets": "New York Mets",
            "ny-yankees": "New York Yankees",
            "phi-phillies": "Philadelphia Phillies",
            "pit-pirates": "Pittsburgh Pirates",
            "sd-padres": "San Diego Padres",
            "sea-mariners": "Seattle Mariners",
            "sf-giants": "San Francisco Giants",
            "stl-cardinals": "St. Louis Cardinals",
            "tb-rays": "Tampa Bay Rays",
            "tex-rangers": "Texas Rangers",
            "tor-blue-jays": "Toronto Blue Jays",
            "was-nationals": "Washington Nationals",
            "the-athletics": "Athletics",
            "lg-twins": "LG Twins",
            "kiwoom-heroes": "Kiwoom Heroes",
            "ssg-landers": "SSG Landers",
            "doosan-bears": "Doosan Bears",
            "samsung-lions": "Samsung Lions",
            "kia-tigers": "Kia Tigers",
            "nc-dinos": "NC Dinos",
            "kt-wiz": "KT Wiz",
            "hanwha-eagles": "Hanwha Eagles",
            "lotte-giants": "Lotte Giants",
        }
        body = slug.replace("-vs-", "|").replace("-at-", "|")
        if "|" not in body:
            return "", ""
        left, right = body.split("|", 1)
        home = aliases.get(left, " ".join(part.capitalize() for part in left.split("-")))
        away = aliases.get(right, " ".join(part.capitalize() for part in right.split("-")))
        return home, away

    def build_event_payload(self, event: UnibetBaseballEvent) -> dict[str, Any]:
        markets = self.get_event_markets(event.url)
        # Prefer richer extract_all if available
        try:
            html = self.get_event_html(event.url)
            all_markets = self.extract_all_event_markets_from_html(html)
            if len(all_markets) > len(markets):
                markets = all_markets
        except Exception:
            pass
        merged: dict[str, UnibetMarket] = {}
        for market in markets:
            existing = merged.get(market.label)
            if existing is None or len(market.outcomes) > len(existing.outcomes):
                merged[market.label] = market
        market_list = list(merged.values())
        return {
            "url": event.url,
            "event_id": event.event_id,
            "name": event.name,
            "home_team": event.home_team,
            "away_team": event.away_team,
            "start_date": event.start_date,
            "competition": event.competition,
            "roster": [],
            "market_count": len(market_list),
            "markets": [
                {
                    "label": market.label,
                    "outcomes": [(o.label, o.odds) for o in market.outcomes],
                }
                for market in market_list
            ],
        }
