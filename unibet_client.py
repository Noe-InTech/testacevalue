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
    selection_id: str = ""


@dataclass(frozen=True)
class UnibetMarket:
    label: str
    outcomes: tuple[UnibetOutcome, ...]


_SELECTION_OBJECT_RE = re.compile(
    r'\{"id":(\d+),"description":"((?:\\.|[^"\\])*)","parent":"[^"]*","pos":\d+,'
    r'"price":"([^"]+)"[^}]*?"marketDesc":"((?:\\.|[^"\\])*)"',
)


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

    def extract_selection_catalog(
        self, html: str
    ) -> dict[tuple[str, str], tuple[str, float]]:
        """Index (marketDesc, outcomeDesc) -> (selection_id, odds)."""
        catalog: dict[tuple[str, str], tuple[str, float]] = {}
        for match in _SELECTION_OBJECT_RE.finditer(html):
            selection_id, description, price, market_desc = match.groups()
            odds = self._parse_decimal_odds(price)
            if odds is None:
                continue
            key = (market_desc.strip(), description.strip())
            catalog[key] = (selection_id, odds)
        return catalog

    def _attach_selection_ids(
        self,
        markets: list[UnibetMarket],
        catalog: dict[tuple[str, str], tuple[str, float]],
    ) -> list[UnibetMarket]:
        if not catalog:
            return markets
        # Fallback when labels were rewritten (ex. "Plus" -> "Plus 22.5"): unique price in market.
        by_market_price: dict[tuple[str, float], list[str]] = {}
        by_outcome_label: dict[str, list[tuple[str, str]]] = {}
        for (market_desc, desc), (selection_id, odds) in catalog.items():
            by_market_price.setdefault((market_desc, round(float(odds), 3)), []).append(
                selection_id
            )
            by_outcome_label.setdefault(desc, []).append((market_desc, selection_id))
        enriched: list[UnibetMarket] = []
        for market in markets:
            outcomes: list[UnibetOutcome] = []
            for outcome in market.outcomes:
                selection_id = outcome.selection_id
                if not selection_id:
                    hit = catalog.get((market.label, outcome.label))
                    if hit:
                        selection_id = hit[0]
                if not selection_id and outcome.odds is not None:
                    price_hits = by_market_price.get(
                        (market.label, round(float(outcome.odds), 3)), []
                    )
                    if len(price_hits) == 1:
                        selection_id = price_hits[0]
                # Baseball SSR often merges lines into "Plus / Moins Points - Match"
                # while the catalog keeps "Plus / Moins Point(s) 7,5 - Match".
                if not selection_id:
                    selection_id = self._match_catalog_selection(
                        market_label=market.label,
                        outcome_label=outcome.label,
                        outcome_odds=outcome.odds,
                        catalog=catalog,
                        by_outcome_label=by_outcome_label,
                    )
                outcomes.append(
                    UnibetOutcome(
                        label=outcome.label,
                        odds=outcome.odds,
                        selection_id=selection_id or "",
                    )
                )
            enriched.append(UnibetMarket(label=market.label, outcomes=tuple(outcomes)))
        return enriched

    @staticmethod
    def _match_catalog_selection(
        *,
        market_label: str,
        outcome_label: str,
        outcome_odds: float | None,
        catalog: dict[tuple[str, str], tuple[str, float]],
        by_outcome_label: dict[str, list[tuple[str, str]]],
    ) -> str:
        label = str(outcome_label or "").strip()
        if not label:
            return ""
        candidates = by_outcome_label.get(label) or []
        if not candidates:
            return ""
        market_l = str(market_label or "").strip().lower()
        # Prefer catalog markets that share distinctive tokens with the SSR card.
        tokens = [
            token
            for token in ("plus / moins", "face à face", "handicap", "inning", "point")
            if token in market_l
        ]

        def related(market_desc: str) -> bool:
            desc_l = market_desc.lower()
            if not tokens:
                return True
            return any(token in desc_l for token in tokens)

        related_hits = [
            (market_desc, selection_id)
            for market_desc, selection_id in candidates
            if related(market_desc)
        ]
        pool = related_hits or candidates
        if len(pool) == 1:
            return pool[0][1]
        # Disambiguate via line embedded in outcome ("Plus 7,5") or unique odds.
        line_match = re.search(r"(\d+[.,]\d+|\d+)", label)
        if line_match:
            line_token = line_match.group(1).replace(".", ",")
            line_token_alt = line_match.group(1).replace(",", ".")
            lined = [
                selection_id
                for market_desc, selection_id in pool
                if line_token in market_desc or line_token_alt in market_desc
            ]
            if len(lined) == 1:
                return lined[0]
        if outcome_odds is not None:
            priced = [
                selection_id
                for market_desc, selection_id in pool
                if (market_desc, label) in catalog
                and abs(float(catalog[(market_desc, label)][1]) - float(outcome_odds)) < 0.02
            ]
            if len(priced) == 1:
                return priced[0]
        return ""

    @staticmethod
    def markets_to_payload(markets: list[UnibetMarket]) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for market in markets:
            selection_ids = {
                outcome.label: outcome.selection_id
                for outcome in market.outcomes
                if outcome.selection_id
            }
            item: dict[str, Any] = {
                "label": market.label,
                "outcomes": [(outcome.label, outcome.odds) for outcome in market.outcomes],
            }
            if selection_ids:
                item["selection_ids"] = selection_ids
            payload.append(item)
        return payload

    def extract_event_markets_from_html(self, html: str) -> list[UnibetMarket]:
        markets: list[UnibetMarket] = []
        pattern = re.compile(
            r'<div class="psel-market-card">.*?'
            r'<span class="psel-title-market__label"[^>]*>(.*?)</span>.*?'
            r'<div class="psel-market-content">(.*?)</div></div>',
            flags=re.S,
        )
        catalog = self.extract_selection_catalog(html)
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
                selection_id = ""
                hit = catalog.get((market_label, label))
                if hit:
                    selection_id = hit[0]
                outcomes.append(
                    UnibetOutcome(label=label, odds=odds, selection_id=selection_id)
                )
            if outcomes:
                markets.append(UnibetMarket(label=market_label, outcomes=tuple(outcomes)))
        return markets

    def extract_embedded_markets_from_html(self, html: str) -> list[UnibetMarket]:
        """Marchés LVS embarqués (live) absents des cartes SSR — avec selection_id."""
        grouped: dict[str, dict[str, UnibetOutcome]] = {}
        catalog = self.extract_selection_catalog(html)
        for (market_desc, description), (selection_id, odds) in catalog.items():
            # Prefer aces-like markets for tennis embedded path; keep all for catalog attach.
            if "ace" not in market_desc.lower() and "aces" not in market_desc.lower():
                # Still useful for ID attach on SSR cards; skip building full market noise.
                continue
            bucket = grouped.setdefault(market_desc, {})
            bucket[description] = UnibetOutcome(
                label=description,
                odds=odds,
                selection_id=selection_id,
            )
        # Also keep legacy regex for labels that miss the compact object form.
        for match in re.finditer(
            r'"description":"((?:Plus / Moins \(Aces\)[^"]+|Plus / Moins Ace\(s\)[^"]+))"',
            html,
        ):
            chunk = html[match.start() : match.start() + 2500]
            description = match.group(1)
            period_match = re.search(r'"period":"([^"]*)"', chunk)
            period = period_match.group(1).strip() if period_match else ""
            label = description if not period or period in description else f"{description} - {period}"
            bucket = grouped.setdefault(label, {})
            for outcome_match in re.finditer(
                r'"description":"([^"]+)"[^}]*?"price":"([^"]+)"',
                chunk,
            ):
                odds = self._parse_decimal_odds(outcome_match.group(2))
                if odds is None:
                    continue
                outcome_label = outcome_match.group(1)
                selection_id = ""
                hit = catalog.get((label, outcome_label)) or catalog.get((description, outcome_label))
                if hit:
                    selection_id = hit[0]
                previous = bucket.get(outcome_label)
                if previous is None or (not previous.selection_id and selection_id):
                    bucket[outcome_label] = UnibetOutcome(
                        label=outcome_label,
                        odds=odds,
                        selection_id=selection_id,
                    )
        return [
            UnibetMarket(label=label, outcomes=tuple(outcomes.values()))
            for label, outcomes in grouped.items()
            if outcomes
        ]

    def extract_all_event_markets_from_html(self, html: str) -> list[UnibetMarket]:
        catalog = self.extract_selection_catalog(html)
        merged: dict[str, UnibetMarket] = {}
        for market in self.extract_event_markets_from_html(html) + self.extract_embedded_markets_from_html(html):
            existing = merged.get(market.label)
            if existing is None or len(market.outcomes) > len(existing.outcomes):
                merged[market.label] = market
            elif existing is not None:
                # Prefer variants that carry more selection_ids.
                existing_ids = sum(1 for outcome in existing.outcomes if outcome.selection_id)
                new_ids = sum(1 for outcome in market.outcomes if outcome.selection_id)
                if new_ids > existing_ids:
                    merged[market.label] = market
        return self._attach_selection_ids(list(merged.values()), catalog)

    def get_event_markets(self, event_url: str) -> list[UnibetMarket]:
        html = self.get_event_html(event_url)
        return self.extract_all_event_markets_from_html(html)

    @staticmethod
    def _is_live_event_url(url: str) -> bool:
        return "/paris-en-direct/" in url

    def derive_prematch_urls(self, url: str) -> list[str]:
        match = re.search(r"/paris-en-direct/(\d+)/([^/?#]+)", url)
        if not match:
            return []
        event_id, slug = match.group(1), match.group(2)
        candidates: list[str] = []
        for competition_path in self.list_tennis_competition_paths():
            candidates.append(f"{self.base_url}{competition_path}/{event_id}/{slug}")
        return candidates

    def event_fetch_urls(self, event_meta: dict[str, Any]) -> list[str]:
        ordered: list[str] = []
        for raw in list(event_meta.get("urls") or []) + [str(event_meta.get("url", ""))]:
            url = str(raw or "").strip()
            if not url or url in ordered:
                continue
            ordered.append(url)
        for url in list(ordered):
            if self._is_live_event_url(url):
                for candidate in self.derive_prematch_urls(url):
                    if candidate not in ordered:
                        ordered.append(candidate)
        return sorted(ordered, key=lambda url: (1 if self._is_live_event_url(url) else 0, url))

    def build_event_payload(self, event_meta: dict[str, Any]) -> dict[str, Any]:
        merged: dict[str, UnibetMarket] = {}
        fetch_urls = self.event_fetch_urls(event_meta)
        for url in fetch_urls:
            try:
                for market in self.get_event_markets(url):
                    existing = merged.get(market.label)
                    if existing is None or len(market.outcomes) > len(existing.outcomes):
                        merged[market.label] = market
            except RuntimeError:
                continue
        markets = list(merged.values())
        return {
            "url": event_meta.get("url", fetch_urls[0] if fetch_urls else ""),
            "fetch_urls": fetch_urls,
            "name": event_meta.get("name", ""),
            "home_player": event_meta.get("home", ""),
            "away_player": event_meta.get("away", ""),
            "start_date": event_meta.get("start_date", ""),
            "competition": event_meta.get("competition", ""),
            "market_count": len(markets),
            "markets": self.markets_to_payload(markets),
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
            html = ""
        paths = {
            match.group(1).rstrip("/")
            for match in re.finditer(
                r'href="(/paris-tennis/(?:atp|wta)/[^"/?#]+)"',
                html,
                flags=re.I,
            )
        }
        if paths:
            return sorted(paths)
        try:
            for event in self.list_tennis_events_from_html_links(path):
                url = str(event.get("url", ""))
                competition_match = re.search(r"/paris-tennis/((?:atp|wta)/[^/]+)/", url, flags=re.I)
                if competition_match:
                    paths.add(f"/paris-tennis/{competition_match.group(1).rstrip('/')}")
        except RuntimeError:
            pass
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
            if existing is None:
                events_by_key[key] = {**item, "urls": [url]}
                return
            urls = existing.setdefault("urls", [existing.get("url", "")])
            if url and url not in urls:
                urls.append(url)
            if self._event_url_priority(url) > self._event_url_priority(existing.get("url", "")):
                for field in ("url", "name", "start_date", "competition", "is_live"):
                    if field in item:
                        existing[field] = item[field]

        self._ingest_listing_path(path, ingest)
        for competition_path in self.list_tennis_competition_paths(path):
            self._ingest_listing_path(competition_path, ingest)

        return sorted(events_by_key.values(), key=lambda event: event.get("start_date", ""))

    def list_prematch_singles_tennis_events(self) -> list[dict[str, Any]]:
        return [event for event in self.list_singles_tennis_events() if not self._event_is_live(event)]

    @staticmethod
    def _event_is_live(event: dict[str, Any]) -> bool:
        if event.get("is_live"):
            return True
        urls = [str(url) for url in (event.get("urls") or []) if url]
        primary = str(event.get("url", "")).strip()
        if primary and primary not in urls:
            urls.append(primary)
        if not urls:
            return False
        return all("/paris-en-direct/" in url for url in urls)

    @staticmethod
    def _event_url_priority(url: str) -> tuple[int, int]:
        score = 0
        if "/cotes-boostees/" in url:
            score -= 100
        if "/atp/" in url or "/wta/" in url:
            score += 10
        if "/paris-en-direct/" in url:
            score += 5
        return score, -len(url)
