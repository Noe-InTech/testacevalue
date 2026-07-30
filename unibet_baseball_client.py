"""Client Unibet FR — baseball / MLB / KBO / NPB."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from baseball_constants import (
    UNIBET_BASEBALL_LISTING_PATH,
    UNIBET_KBO_LISTING_PATH,
    UNIBET_MLB_LISTING_PATH,
    UNIBET_NPB_LISTING_PATH,
)
from baseball_listings import competition_from_blob, is_baseball_outright_name
from baseball_market_mapping import normalize_person_name
from unibet_client import UnibetClient, UnibetMarket, UnibetOutcome

_EMBEDDED_OUTCOME_BLOCK_RE = re.compile(
    r'\{[^{}]*?"marketDesc":"([^"]+)"[^{}]*?\}',
    flags=re.I,
)


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

    def list_npb_events(self) -> list[UnibetBaseballEvent]:
        events: dict[str, UnibetBaseballEvent] = {}
        try:
            html = self.get_tennis_listing_html(UNIBET_NPB_LISTING_PATH)
        except Exception:
            return []
        self._ingest_paths(
            html,
            events,
            pattern=r'href="(/paris-baseball/japon/npb/\d+/[^"#?]+)"',
            competition="NPB",
        )
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
            if competition_from_blob(slug, home, away) != "NPB":
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
                    competition="NPB",
                )
        return sorted(events.values(), key=lambda item: item.name)

    def list_baseball_events(self) -> list[UnibetBaseballEvent]:
        merged: dict[str, UnibetBaseballEvent] = {}
        for event in [
            *self.list_mlb_events(),
            *self.list_kbo_events(),
            *self.list_npb_events(),
        ]:
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
            # NPB
            "chiba-lotte-marines": "Chiba Lotte Marines",
            "chunichi-dragons": "Chunichi Dragons",
            "fukuoka-softbank-hawks": "Fukuoka SoftBank Hawks",
            "hanshin-tigers": "Hanshin Tigers",
            "hiroshima-carp": "Hiroshima Carp",
            "hokkaido-nippon-ham-fighters": "Hokkaido Nippon-Ham Fighters",
            "nippon-ham-fighters": "Hokkaido Nippon-Ham Fighters",
            "orix-buffaloes": "Orix Buffaloes",
            "rakuten-eagles": "Rakuten Eagles",
            "tohoku-rakuten-golden-eagles": "Tohoku Rakuten Golden Eagles",
            "saitama-seibu-lions": "Saitama Seibu Lions",
            "seibu-lions": "Saitama Seibu Lions",
            "tokyo-yakult-swallows": "Tokyo Yakult Swallows",
            "yakult-swallows": "Tokyo Yakult Swallows",
            "yokohama-baystars": "Yokohama BayStars",
            "yomiuri-giants": "Yomiuri Giants",
        }
        body = slug.replace("-vs-", "|").replace("-at-", "|")
        if "|" not in body:
            return "", ""
        left, right = body.split("|", 1)
        home = aliases.get(left, " ".join(part.capitalize() for part in left.split("-")))
        away = aliases.get(right, " ".join(part.capitalize() for part in right.split("-")))
        return home, away

    def build_event_payload(self, event: UnibetBaseballEvent) -> dict[str, Any]:
        html = ""
        try:
            html = self.get_event_html(event.url)
        except Exception:
            html = ""

        markets = self.get_event_markets(event.url) if not html else []
        if html:
            try:
                markets = self.extract_all_event_markets_from_html(html)
            except Exception:
                markets = self.get_event_markets(event.url)

        player_markets = (
            self.extract_baseball_player_markets_from_html(html) if html else []
        )

        merged: dict[str, UnibetMarket] = {}
        for market in markets:
            # Drop anonymous SSR HR board — embedded per-player markets replace it.
            if strip_home_runs_joueur(market.label) and not player_has_named_outcomes(
                market
            ):
                continue
            existing = merged.get(market.label)
            if existing is None or len(market.outcomes) > len(existing.outcomes):
                merged[market.label] = market
        for market in player_markets:
            existing = merged.get(market.label)
            if existing is None or len(market.outcomes) > len(existing.outcomes):
                merged[market.label] = market

        market_list = list(merged.values())
        roster = self._extract_roster_from_markets(market_list)
        return {
            "url": event.url,
            "event_id": event.event_id,
            "name": event.name,
            "home_team": event.home_team,
            "away_team": event.away_team,
            "start_date": event.start_date,
            "competition": event.competition,
            "roster": roster,
            "market_count": len(market_list),
            "markets": [
                {
                    "label": market.label,
                    "outcomes": [(o.label, o.odds) for o in market.outcomes],
                }
                for market in market_list
            ],
        }

    def extract_baseball_player_markets_from_html(self, html: str) -> list[UnibetMarket]:
        """Per-player HR (and similar) markets from embedded LVS JSON."""
        grouped: dict[str, dict[str, UnibetOutcome]] = defaultdict(dict)
        for market_desc, description, odds in self._iter_embedded_outcome_blocks(html):
            if odds is None:
                continue
            lower = market_desc.lower()
            if not self._is_player_hr_market_desc(lower):
                continue
            if any(
                token in lower
                for token in ("double chance", "triple chance", "duo", "trio")
            ):
                continue
            grouped[market_desc][description] = UnibetOutcome(
                label=description,
                odds=odds,
            )
        markets: list[UnibetMarket] = []
        for label, outcomes in grouped.items():
            if not outcomes:
                continue
            markets.append(
                UnibetMarket(label=label, outcomes=tuple(outcomes.values()))
            )
        return markets

    def _iter_embedded_outcome_blocks(self, html: str):
        # Blocks where marketDesc appears after description/price — also scan
        # reverse-order objects via a looser pass on description+price+marketDesc.
        seen: set[tuple[str, str, float]] = set()
        for match in _EMBEDDED_OUTCOME_BLOCK_RE.finditer(html):
            block = match.group(0)
            market_desc = self._extract_json_string(block, "marketDesc")
            description = self._extract_json_string(block, "description")
            if not market_desc or not description:
                continue
            odds = self._parse_decimal_odds(
                self._extract_json_string(block, "price") or ""
            )
            if odds is None:
                continue
            key = (market_desc.strip(), description.strip(), float(odds))
            if key in seen:
                continue
            seen.add(key)
            yield market_desc.strip(), description.strip(), odds

        # Fallback: description may precede marketDesc outside a single flat object
        # when nested braces break the simple regex — pair nearby fields.
        for match in re.finditer(
            r'"description":"([^"]+)"[\s\S]{0,240}?"price":"([^"]+)"[\s\S]{0,240}?"marketDesc":"([^"]+)"',
            html,
            flags=re.I,
        ):
            description, price, market_desc = (
                match.group(1).strip(),
                match.group(2),
                match.group(3).strip(),
            )
            odds = self._parse_decimal_odds(price)
            if odds is None:
                continue
            key = (market_desc, description, float(odds))
            if key in seen:
                continue
            seen.add(key)
            yield market_desc, description, odds

    @staticmethod
    def _extract_json_string(block: str, key: str) -> str | None:
        field = re.search(rf'"{re.escape(key)}":"([^"]*)"', block)
        return field.group(1).strip() if field else None

    @staticmethod
    def _is_player_hr_market_desc(lower: str) -> bool:
        if "nombre de home runs" not in lower:
            return False
        # Per-player: "Nombre de Home Runs- Contreras, Willson - Match"
        return bool(
            re.search(r"nombre de home runs\s*-\s*.+\s*-\s*match", lower)
        )

    @staticmethod
    def _extract_roster_from_markets(markets: list[UnibetMarket]) -> list[str]:
        roster: list[str] = []
        for market in markets:
            player_from_label = re.search(
                r"nombre de home runs\s*-\s*(.+?)\s*-\s*match",
                market.label,
                flags=re.I,
            )
            if player_from_label:
                roster.append(normalize_person_name(player_from_label.group(1)))
            for outcome in market.outcomes:
                tier = re.match(r"(.+?)\s+(\d+)\+$", outcome.label.strip())
                if tier:
                    roster.append(normalize_person_name(tier.group(1)))
        return sorted({name for name in roster if name})


def strip_home_runs_joueur(label: str) -> bool:
    lower = re.sub(r"\s+", " ", label.strip().lower())
    return lower in {
        "nombre de home runs - joueur",
        "nombre de home runs- joueur",
    }


def player_has_named_outcomes(market: UnibetMarket) -> bool:
    for outcome in market.outcomes:
        if re.search(r"[A-Za-z].*\d+\+", outcome.label):
            return True
        if "," in outcome.label and re.search(r"\d+\+", outcome.label):
            return True
    return False
