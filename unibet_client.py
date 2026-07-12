"""Client pour le front sportsbook Unibet FR."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import requests

BASE_URL = "https://www.unibet.fr"
DEFAULT_USER_AGENT = "Mozilla/5.0"
TOKEN_PATH = "/lvs-api/acc/token"
EPT_PATH = "/lvs-api/ept"
EPT_QUERY = {
    "originId": "3",
    "lineId": "1",
    "up": "1",
    "hidden": "0",
    "liveCount": "e",
    "preCount": "e",
    "status": "OPEN,SUSPENDED",
    "clockStatus": "NOT_STARTED,STARTED,PAUSED,END_OF_PERIOD,ADJUST,INTERMISSION",
    "includeAllMarkets": "1",
}


@dataclass(frozen=True)
class UnibetCompetition:
    sport_code: str
    category_name: str
    competition_id: int
    competition_name: str
    event_count: int


@dataclass(frozen=True)
class UnibetOutcome:
    label: str
    odds: float | None


@dataclass(frozen=True)
class UnibetMarket:
    label: str
    outcomes: tuple[UnibetOutcome, ...]


class UnibetClient:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": DEFAULT_USER_AGENT})
        self._hs_token: str | None = None

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def get_hs_token(self, force_refresh: bool = False) -> str:
        if self._hs_token and not force_refresh:
            return self._hs_token
        response = self.session.get(self._url(TOKEN_PATH), timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"Unibet token API {response.status_code}: {response.text[:200]}")
        payload = response.json()
        token = str(payload.get("hsToken", "")).strip()
        if not token:
            raise RuntimeError("Unibet token manquant dans /lvs-api/acc/token")
        self._hs_token = token
        return token

    def _get_lvs(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        token = self.get_hs_token()
        response = self.session.get(
            self._url(path),
            params=params,
            headers={"X-LVS-HSToken": token},
            timeout=30,
        )
        if response.status_code == 401:
            token = self.get_hs_token(force_refresh=True)
            response = self.session.get(
                self._url(path),
                params=params,
                headers={"X-LVS-HSToken": token},
                timeout=30,
            )
        if response.status_code != 200:
            raise RuntimeError(f"Unibet LVS API {response.status_code}: {response.text[:200]}")
        return response.json()

    def get_event_path_tree(self) -> dict[str, Any]:
        return self._get_lvs(EPT_PATH, EPT_QUERY)

    def list_tennis_competitions(self) -> list[UnibetCompetition]:
        payload = self.get_event_path_tree()
        competitions: list[UnibetCompetition] = []
        for sport in payload.get("ept", []):
            if sport.get("code") != "TENN":
                continue
            for category in sport.get("path", []):
                category_name = str(category.get("desc", ""))
                for competition in category.get("path", []):
                    competitions.append(
                        UnibetCompetition(
                            sport_code=str(sport.get("code", "")),
                            category_name=category_name,
                            competition_id=int(competition["id"]),
                            competition_name=str(competition.get("desc", "")),
                            event_count=int(competition.get("count", 0) or 0),
                        )
                    )
        competitions.sort(key=lambda item: (item.category_name, item.competition_name))
        return competitions

    def get_tennis_listing_html(self, path: str = "/paris-tennis") -> str:
        response = self.session.get(self._url(path), timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"Unibet page {response.status_code}: {response.text[:200]}")
        return response.text

    def list_tennis_event_urls(self, path: str = "/paris-tennis") -> list[str]:
        html = self.get_tennis_listing_html(path)
        urls = sorted(
            {
                f"{self.base_url}{match}"
                for match in re.findall(r'href="(/paris-tennis/[^"]+)"', html)
                if match.count("/") >= 4
            }
        )
        return urls

    def extract_json_ld_events(self, html: str) -> list[dict[str, Any]]:
        match = re.search(
            r'<script id="sport-main-jsonLd" type="application/ld\+json">(.*?)</script>',
            html,
            flags=re.S,
        )
        if not match:
            return []
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            return []
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            return [payload]
        return []

    def list_tennis_events_from_json_ld(self, path: str = "/paris-tennis") -> list[dict[str, Any]]:
        html = self.get_tennis_listing_html(path)
        events = []
        for item in self.extract_json_ld_events(html):
            name = str(item.get("name", "")).strip()
            url = str(item.get("url", "")).strip()
            if not name or not url:
                continue
            events.append(
                {
                    "name": name,
                    "url": url,
                    "start_date": item.get("startDate", ""),
                    "competition": ((item.get("location") or {}).get("name", "")),
                    "home": ((item.get("homeTeam") or {}).get("name", "")),
                    "away": ((item.get("awayTeam") or {}).get("name", "")),
                }
            )
        return events

    def get_event_html(self, event_url: str) -> str:
        response = self.session.get(event_url, timeout=30)
        if response.status_code not in (200, 302) or not response.text:
            raise RuntimeError(f"Unibet event page {response.status_code}: {response.text[:200]}")
        return response.text

    @staticmethod
    def _strip_html(value: str) -> str:
        text = re.sub(r"<[^>]+>", " ", value)
        text = text.replace("&nbsp;", " ")
        return " ".join(text.split()).strip()

    @staticmethod
    def _parse_decimal_odds(value: str) -> float | None:
        cleaned = value.strip().replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None

    def extract_event_markets_from_html(self, html: str) -> list[UnibetMarket]:
        markets: list[UnibetMarket] = []
        pattern = re.compile(
            r'<div class="psel-market-card">.*?'
            r'<span class="psel-title-market__label"[^>]*>(.*?)</span>.*?'
            r'<div class="psel-market-content">(.*?)</div></div>',
            flags=re.S,
        )
        for market_label_html, market_content in pattern.findall(html):
            market_label = self._strip_html(market_label_html)
            if not market_label:
                continue
            outcomes: list[UnibetOutcome] = []
            for label_html, odds_html in re.findall(
                r'<span class="psel-outcome__label">(.*?)</span>.*?'
                r'<span class="psel-outcome__data">(.*?)</span>',
                market_content,
                flags=re.S,
            ):
                label = self._strip_html(label_html)
                odds = self._parse_decimal_odds(self._strip_html(odds_html))
                if not label:
                    continue
                outcomes.append(UnibetOutcome(label=label, odds=odds))
            if outcomes:
                markets.append(UnibetMarket(label=market_label, outcomes=tuple(outcomes)))
        return markets

    def get_event_markets(self, event_url: str) -> list[UnibetMarket]:
        html = self.get_event_html(event_url)
        return self.extract_event_markets_from_html(html)

    def build_event_payload(self, event_meta: dict[str, Any]) -> dict[str, Any]:
        markets = self.get_event_markets(event_meta["url"])
        return {
            "url": event_meta["url"],
            "name": event_meta.get("name", ""),
            "home_player": event_meta.get("home", ""),
            "away_player": event_meta.get("away", ""),
            "start_date": event_meta.get("start_date", ""),
            "competition": event_meta.get("competition", ""),
            "market_count": len(markets),
            "markets": [
                {"label": market.label, "outcomes": [(o.label, o.odds) for o in market.outcomes]}
                for market in markets
            ],
        }

    def list_tennis_events_from_html_links(self, path: str) -> list[dict[str, Any]]:
        html = self.get_tennis_listing_html(path)
        events: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        def add_event(href: str, name: str, competition: str) -> None:
            name = self._strip_html(name)
            competition = self._strip_html(competition)
            if not href or href in seen_urls:
                return
            home = ""
            away = ""
            if " - " in name:
                home, away = [part.strip() for part in name.split(" - ", 1)]
            elif re.search(r"\s+vs\s+", name, flags=re.I):
                parts = re.split(r"\s+vs\s+", name, flags=re.I)
                if len(parts) == 2:
                    home, away = parts[0].strip(), parts[1].strip()
            if not home or not away:
                slug = href.rsplit("/", 1)[-1]
                slug_match = re.match(r"^[a-z]-(.+)-vs-([a-z]-.+)$", slug, flags=re.I)
                if slug_match:
                    home = slug_match.group(1).replace("-", " ").title()
                    away = slug_match.group(2).replace("-", " ").title()
            if not home or not away:
                return
            seen_urls.add(href)
            events.append(
                {
                    "name": name or f"{home} - {away}",
                    "url": f"{self.base_url}{href}",
                    "start_date": "",
                    "competition": competition,
                    "home": home,
                    "away": away,
                    "is_live": "/paris-en-direct/" in href,
                }
            )

        title_patterns = (
            re.compile(
                r'href="(/paris-(?:tennis|en-direct)/[^"]+)"[^>]*title="[^"]*?:\s*([^|"]+)\s*\|\s*([^"]+)"',
                flags=re.I,
            ),
            re.compile(
                r'title="[^"]*?:\s*([^|"]+)\s*\|\s*([^"]+)"[^>]*href="(/paris-(?:tennis|en-direct)/[^"]+)"',
                flags=re.I,
            ),
        )
        for pattern in title_patterns:
            for match in pattern.findall(html):
                if len(match) == 3 and match[0].startswith("/paris-"):
                    add_event(match[0], match[1], match[2])
                else:
                    add_event(match[2], match[0], match[1])

        for href in re.findall(r'href="(/paris-(?:tennis|en-direct)/[^"]+)"', html):
            if href in seen_urls:
                continue
            if href.count("/") < 4:
                continue
            add_event(href, "", "")

        return events

    def list_tennis_competition_paths(self, path: str = "/paris-tennis") -> list[str]:
        try:
            html = self.get_tennis_listing_html(path)
        except RuntimeError:
            return []
        paths = {
            match.group(1).rstrip("/")
            for match in re.finditer(
                r'href="(/paris-tennis/(?:atp|wta)/[^"/?#]+)"',
                html,
                flags=re.I,
            )
        }
        return sorted(paths)

    def _ingest_listing_path(
        self,
        listing_path: str,
        ingest: Any,
    ) -> None:
        try:
            for item in self.list_tennis_events_from_json_ld(listing_path):
                ingest(item)
        except RuntimeError:
            pass
        try:
            for item in self.list_tennis_events_from_html_links(listing_path):
                ingest(item)
        except RuntimeError:
            pass

    def list_singles_tennis_events(self, path: str = "/paris-tennis") -> list[dict[str, Any]]:
        events_by_key: dict[str, dict[str, Any]] = {}

        def ingest(item: dict[str, Any]) -> None:
            name = str(item.get("name", ""))
            home = str(item.get("home", ""))
            away = str(item.get("away", ""))
            url = str(item.get("url", ""))
            if "/cotes-boostees/" in url:
                return
            if "/" in name or "/" in home or "/" in away:
                return
            if " & " in name or " et " in name.lower():
                return
            key = f"{home}|{away}".lower()
            existing = events_by_key.get(key)
            if existing is None or self._event_url_priority(url) > self._event_url_priority(existing["url"]):
                events_by_key[key] = item

        self._ingest_listing_path(path, ingest)
        for competition_path in self.list_tennis_competition_paths(path):
            self._ingest_listing_path(competition_path, ingest)

        return sorted(events_by_key.values(), key=lambda event: event.get("start_date", ""))

    @staticmethod
    def _event_url_priority(url: str) -> tuple[int, int]:
        score = 0
        if "/cotes-boostees/" in url:
            score -= 100
        if "/atp/" in url or "/wta/" in url:
            score += 10
        if "/paris-en-direct/" in url:
            score += 20
        return score, -len(url)
