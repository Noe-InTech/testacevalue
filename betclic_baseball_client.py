"""Client Betclic FR — baseball / MLB / KBO."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from baseball_constants import (
    BETCLIC_BASEBALL_LISTING_PATHS,
    BETCLIC_BASEBALL_MATCH_HREF_RE,
)
from baseball_listings import competition_from_blob, is_baseball_outright_name
from betclic_client import BetclicClient

# Longest slugs first for greedy matching in team-token parse.
BASEBALL_TEAM_SLUGS: tuple[tuple[str, str], ...] = tuple(
    sorted(
        (
            # MLB
            ("arizona-diamondbacks", "Arizona Diamondbacks"),
            ("atlanta-braves", "Atlanta Braves"),
            ("baltimore-orioles", "Baltimore Orioles"),
            ("boston-red-sox", "Boston Red Sox"),
            ("chicago-cubs", "Chicago Cubs"),
            ("chicago-white-sox", "Chicago White Sox"),
            ("cincinnati-reds", "Cincinnati Reds"),
            ("cleveland-guardians", "Cleveland Guardians"),
            ("colorado-rockies", "Colorado Rockies"),
            ("detroit-tigers", "Detroit Tigers"),
            ("houston-astros", "Houston Astros"),
            ("kansas-city-royals", "Kansas City Royals"),
            ("los-angeles-angels", "Los Angeles Angels"),
            ("los-angeles-dodgers", "Los Angeles Dodgers"),
            ("miami-marlins", "Miami Marlins"),
            ("milwaukee-brewers", "Milwaukee Brewers"),
            ("minnesota-twins", "Minnesota Twins"),
            ("new-york-mets", "New York Mets"),
            ("new-york-yankees", "New York Yankees"),
            ("oakland-athletics", "Oakland Athletics"),
            ("athletics", "Athletics"),
            ("philadelphia-phillies", "Philadelphia Phillies"),
            ("pittsburgh-pirates", "Pittsburgh Pirates"),
            ("san-diego-padres", "San Diego Padres"),
            ("san-francisco-giants", "San Francisco Giants"),
            ("seattle-mariners", "Seattle Mariners"),
            ("st-louis-cardinals", "St. Louis Cardinals"),
            ("tampa-bay-rays", "Tampa Bay Rays"),
            ("texas-rangers", "Texas Rangers"),
            ("toronto-blue-jays", "Toronto Blue Jays"),
            ("washington-nationals", "Washington Nationals"),
            # KBO
            ("doosan-bears", "Doosan Bears"),
            ("hanwha-eagles", "Hanwha Eagles"),
            ("kia-tigers", "Kia Tigers"),
            ("kiwoom-heroes", "Kiwoom Heroes"),
            ("kt-wiz", "KT Wiz"),
            ("lg-twins", "LG Twins"),
            ("lotte-giants", "Lotte Giants"),
            ("nc-dinos", "NC Dinos"),
            ("samsung-lions", "Samsung Lions"),
            ("ssg-landers", "SSG Landers"),
        ),
        key=lambda item: len(item[0]),
        reverse=True,
    )
)


@dataclass(frozen=True)
class BetclicBaseballMatchLink:
    match_id: str
    url: str
    slug: str
    home_team: str
    away_team: str
    competition: str = ""


class BetclicBaseballClient(BetclicClient):
    def list_mlb_matches(self) -> list[BetclicBaseballMatchLink]:
        return [
            link
            for link in self.list_baseball_matches()
            if link.competition == "MLB"
        ]

    def list_kbo_matches(self) -> list[BetclicBaseballMatchLink]:
        return [
            link
            for link in self.list_baseball_matches()
            if link.competition == "KBO"
        ]

    def list_baseball_matches(self) -> list[BetclicBaseballMatchLink]:
        links: dict[str, BetclicBaseballMatchLink] = {}
        errors: list[str] = []
        for path in BETCLIC_BASEBALL_LISTING_PATHS:
            try:
                html = self.get_page_html(path)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{path}: {exc}")
                continue
            for href in BETCLIC_BASEBALL_MATCH_HREF_RE.findall(html):
                parsed = self._parse_match_href(href)
                if parsed is None:
                    continue
                links[parsed.match_id] = parsed
        if not links and errors:
            raise RuntimeError(
                "Betclic baseball listing indisponible: " + " | ".join(errors[:3])
            )
        return sorted(links.values(), key=lambda item: item.url)

    def _parse_match_href(self, href: str) -> BetclicBaseballMatchLink | None:
        match = re.search(r"-m(\d+)$", href)
        if not match:
            return None
        slug = href.rsplit("/", 1)[-1]
        if is_baseball_outright_name(slug):
            return None
        home, away = self._teams_from_slug(slug)
        if not home or not away:
            return None
        competition = competition_from_blob(href, home, away)
        if competition not in {"MLB", "KBO"}:
            return None
        return BetclicBaseballMatchLink(
            match_id=match.group(1),
            url=f"{self.base_url}{href}",
            slug=slug,
            home_team=home,
            away_team=away,
            competition=competition,
        )

    @classmethod
    def _teams_from_slug(cls, slug: str) -> tuple[str, str]:
        body = re.sub(r"-m\d+$", "", slug).lower()
        for sep in ("-vs-", "-v-"):
            if sep in body:
                left, right = body.split(sep, 1)
                return (
                    cls._name_from_slug_fragment(left),
                    cls._name_from_slug_fragment(right),
                )

        found: list[tuple[int, int, str]] = []
        used: set[int] = set()
        for token, name in BASEBALL_TEAM_SLUGS:
            start = 0
            while True:
                index = body.find(token, start)
                if index < 0:
                    break
                end = index + len(token)
                if any(pos in used for pos in range(index, end)):
                    start = index + 1
                    continue
                # Require slug boundaries (start/end or hyphen).
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

    @classmethod
    def _name_from_slug_fragment(cls, value: str) -> str:
        token = value.strip("-").lower()
        for slug, name in BASEBALL_TEAM_SLUGS:
            if slug == token:
                return name
        return cls._titleize_slug(token)

    @staticmethod
    def _titleize_slug(value: str) -> str:
        cleaned = value.strip("-").replace("-", " ").strip()
        return " ".join(part.capitalize() for part in cleaned.split())

    def build_event_payload(self, link: BetclicBaseballMatchLink) -> dict[str, Any]:
        # None → scrape toutes les catégories gRPC présentes sur le match.
        payload = self.get_full_match_payload(link.url, grpc_categories=None)
        match = payload.get("match") or {}
        contestants = match.get("contestants") or []
        home = link.home_team or (contestants[0].get("name", "") if contestants else "")
        away = link.away_team or (contestants[1].get("name", "") if len(contestants) > 1 else "")
        markets = self.extract_markets_from_match_payload(payload)
        roster = self._extract_roster_from_markets(markets, fallback=[home, away])
        competition = (
            link.competition
            or competition_from_blob(
                str((match.get("competition") or {}).get("name", "")),
                home,
                away,
            )
        )
        return {
            "url": link.url,
            "match_id": link.match_id,
            "name": str(match.get("name", "")) or f"{home} - {away}",
            "home_team": home,
            "away_team": away,
            "start_date": match.get("matchDateUtc", ""),
            "competition": competition,
            "roster": roster,
            "market_count": len(markets),
            "markets": [
                {"label": market.label, "outcomes": [(o.label, o.odds) for o in market.outcomes]}
                for market in markets
            ],
        }

    @staticmethod
    def _extract_roster_from_markets(markets: Any, *, fallback: list[str]) -> list[str]:
        garbage = {"joueur", "equipe", "player", "yes", "no", "oui", "non"}
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
                    if name.lower() not in garbage:
                        roster.append(name)
            parsed = re.search(r"-\s*(.+?)\s*\(([\d.,]+)\)\s*$", market.label)
            if parsed:
                name = parsed.group(1).strip()
                if name.lower() not in garbage:
                    roster.append(name)
        cleaned = sorted({name for name in roster if name})
        return cleaned or [name for name in fallback if name]
