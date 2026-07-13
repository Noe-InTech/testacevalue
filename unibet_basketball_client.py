"""Client Unibet FR — basketball / WNBA."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from basketball_constants import UNIBET_BASKETBALL_LISTING_PATH, UNIBET_NBA_HUB_PATHS
from basketball_listings import is_basketball_outright_slug
from unibet_client import UnibetClient, UnibetMarket, UnibetOutcome

_EMBEDDED_OUTCOME_BLOCK_RE = re.compile(
    r'\{[^{}]*?"marketDesc":"([^"]+)"[^{}]*?\}',
    flags=re.I,
)


@dataclass(frozen=True)
class UnibetBasketballEvent:
    event_id: str
    name: str
    home_team: str
    away_team: str
    url: str
    competition: str = ""
    start_date: str = ""


class UnibetBasketballClient(UnibetClient):
    def list_wnba_events(self) -> list[UnibetBasketballEvent]:
        html = self.get_tennis_listing_html(UNIBET_BASKETBALL_LISTING_PATH)
        events: dict[str, UnibetBasketballEvent] = {}
        for match in re.finditer(
            r'href="(/paris-basketball/usa/wnba/\d+/[^"]+)"',
            html,
            flags=re.I,
        ):
            path = match.group(1)
            if path.rstrip("/").endswith("wnba-2026"):
                continue
            slug = path.rsplit("/", 1)[-1]
            event_id = path.split("/")[-2]
            home, away = self._teams_from_slug(slug)
            if not home or not away:
                continue
            name = f"{home} - {away}"
            key = f"{home}|{away}".lower()
            url = f"{self.base_url}{path}"
            existing = events.get(key)
            if existing is None or len(url) > len(existing.url):
                events[key] = UnibetBasketballEvent(
                    event_id=str(event_id),
                    name=name,
                    home_team=home,
                    away_team=away,
                    url=url,
                    competition="WNBA",
                )
        return sorted(events.values(), key=lambda item: item.name)

    def list_nba_events(self) -> list[UnibetBasketballEvent]:
        events: dict[str, UnibetBasketballEvent] = {}
        pages = [UNIBET_BASKETBALL_LISTING_PATH, *UNIBET_NBA_HUB_PATHS]
        for page in pages:
            html = self.get_tennis_listing_html(page)
            self._ingest_unibet_nba_paths(html, events)
        return sorted(events.values(), key=lambda item: item.name)

    def _ingest_unibet_nba_paths(
        self,
        html: str,
        events: dict[str, UnibetBasketballEvent],
    ) -> None:
        for match in re.finditer(
            r'href="(/paris-basketball/usa/nba/\d+/[^"#?]+)"',
            html,
            flags=re.I,
        ):
            path = match.group(1).rstrip("/")
            if "nba-cup" in path.lower():
                continue
            slug = path.rsplit("/", 1)[-1]
            if is_basketball_outright_slug(slug):
                continue
            event_id = path.split("/")[-2]
            home, away = self._teams_from_nba_slug(slug)
            if not home or not away:
                continue
            name = f"{home} - {away}"
            key = f"{home}|{away}".lower()
            url = f"{self.base_url}{path}"
            existing = events.get(key)
            if existing is None or len(url) > len(existing.url):
                events[key] = UnibetBasketballEvent(
                    event_id=str(event_id),
                    name=name,
                    home_team=home,
                    away_team=away,
                    url=url,
                    competition="NBA",
                )

    @staticmethod
    def _teams_from_nba_slug(slug: str) -> tuple[str, str]:
        body = slug.replace("-vs-", "|").replace("-at-", "|")
        if "|" not in body:
            return "", ""
        left, right = body.split("|", 1)
        return (
            " ".join(part.capitalize() for part in left.split("-")),
            " ".join(part.capitalize() for part in right.split("-")),
        )

    @staticmethod
    def _teams_from_slug(slug: str) -> tuple[str, str]:
        aliases = {
            "atl": "Atlanta Dream",
            "la": "Los Angeles Sparks",
            "min": "Minnesota Lynx",
            "phx": "Phoenix Mercury",
            "con": "Connecticut Sun",
            "por": "Portland Fire",
            "tor": "Toronto Tempo",
            "was": "Washington Mystics",
        }
        body = slug.replace("-vs-", "|")
        if "|" not in body:
            return "", ""
        left, right = body.split("|", 1)
        left_parts = left.split("-")
        right_parts = right.split("-")
        home = aliases.get(left_parts[0], " ".join(part.capitalize() for part in left_parts))
        away = aliases.get(right_parts[0], " ".join(part.capitalize() for part in right_parts))
        return home, away

    def extract_basketball_player_markets_from_html(self, html: str) -> list[UnibetMarket]:
        grouped: dict[str, dict[str, UnibetOutcome]] = defaultdict(dict)

        for market_desc, description, odds in self._iter_embedded_outcome_blocks(html):
            lower = self._strip_html(market_desc).lower()
            if not self._is_player_market_desc(lower):
                continue
            if odds is None or not description:
                continue

            label = description.strip()
            if re.search(r"\d+\+$", label):
                grouped[market_desc][label] = UnibetOutcome(label=label, odds=odds)
                continue
            if not re.search(r"[\d.,]", label):
                continue
            grouped[market_desc][label] = UnibetOutcome(label=label, odds=odds)

        return [
            UnibetMarket(label=market_desc, outcomes=tuple(outcome_map.values()))
            for market_desc, outcome_map in grouped.items()
            if outcome_map
        ]

    def _iter_embedded_outcome_blocks(
        self,
        html: str,
    ):
        for match in _EMBEDDED_OUTCOME_BLOCK_RE.finditer(html):
            block = match.group(0)
            market_desc = self._extract_json_string(block, "marketDesc")
            description = self._extract_json_string(block, "description")
            if not market_desc or not description:
                continue
            odds = self._parse_decimal_odds(self._extract_json_string(block, "price") or "")
            spread_raw = self._extract_json_number(block, "spread")
            if spread_raw is not None and re.match(r"^(?:Plus|Moins)$", description.strip(), flags=re.I):
                description = f"{description.strip()} {spread_raw}"
            yield market_desc.strip(), description.strip(), odds

    @staticmethod
    def _extract_json_string(block: str, key: str) -> str | None:
        field = re.search(rf'"{re.escape(key)}":"([^"]*)"', block)
        return field.group(1).strip() if field else None

    @staticmethod
    def _extract_json_number(block: str, key: str) -> float | None:
        field = re.search(rf'"{re.escape(key)}":(-?[\d.]+)', block)
        if not field:
            return None
        try:
            return float(field.group(1))
        except ValueError:
            return None

    @staticmethod
    def _is_player_market_desc(lower: str) -> bool:
        if " - match" not in lower:
            return False
        if any(token in lower for token in ("double chance", "chaque joueur", "equipe", "handicap")):
            return False
        markers = (
            "plus / moins points -",
            "plus / moins rebonds -",
            "plus / moins passes",
            "paniers 3 pts",
            "+/- paniers",
            "performance joueur",
            "nbre de rebonds - joueur",
            "nbre de passes",
            "paniers a 3 pts reussis - joueur",
            "performance du joueur",
        )
        return any(marker in lower for marker in markers)

    def _parse_ou_outcomes(self, chunk: str) -> list[UnibetOutcome]:
        outcomes: list[UnibetOutcome] = []
        seen: set[str] = set()

        def add_outcome(label: str, odds: float | None) -> None:
            cleaned = label.strip()
            if odds is None or not cleaned:
                return
            if not re.match(r"^(?:Plus|Moins)\b", cleaned, flags=re.I):
                return
            if cleaned in seen:
                return
            seen.add(cleaned)
            outcomes.append(UnibetOutcome(label=cleaned, odds=odds))

        for match in re.finditer(
            r'"description":"((?:Plus|Moins)(?:\s+de)?\s+[\d.,]+)"[^}]*?"price":"([^"]+)"',
            chunk,
            flags=re.I,
        ):
            add_outcome(match.group(1), self._parse_decimal_odds(match.group(2)))

        for match in re.finditer(
            r'"description":"(Plus|Moins)"[^}]*?"(?:handicap|line)":([\d.,]+)[^}]*?"price":"([^"]+)"',
            chunk,
            flags=re.I,
        ):
            side = match.group(1).capitalize()
            line = match.group(2).replace(",", ".")
            add_outcome(f"{side} {line}", self._parse_decimal_odds(match.group(3)))

        for match in re.finditer(
            r'"description":"(Plus|Moins) ([\d.,]+)"[^}]*?"price":"([^"]+)"',
            chunk,
            flags=re.I,
        ):
            side = match.group(1).capitalize()
            line = match.group(2).replace(",", ".")
            add_outcome(f"{side} {line}", self._parse_decimal_odds(match.group(3)))

        if len(outcomes) >= 2:
            by_side: dict[str, float] = {}
            for outcome in outcomes:
                side = "Over" if outcome.label.lower().startswith("plus") else "Under"
                by_side[side] = float(outcome.odds)
            if by_side.get("Over") == by_side.get("Under"):
                return []

        return outcomes

    def _parse_performance_outcomes(self, chunk: str) -> list[UnibetOutcome]:
        outcomes: list[UnibetOutcome] = []
        seen: set[str] = set()
        for match in re.finditer(
            r'"description":"([^"]+)"[^}]*?"price":"([^"]+)"',
            chunk,
        ):
            label = match.group(1).strip()
            if not re.search(r"\d+\+$", label):
                continue
            if label in seen:
                continue
            odds = self._parse_decimal_odds(match.group(2))
            if odds is None:
                continue
            seen.add(label)
            outcomes.append(UnibetOutcome(label=label, odds=odds))
        return outcomes

    def build_event_payload(self, event: UnibetBasketballEvent) -> dict[str, Any]:
        html = self.get_event_html(event.url)
        embedded_markets = self.extract_basketball_player_markets_from_html(html)
        merged: dict[str, UnibetMarket] = {}
        for market in embedded_markets:
            existing = merged.get(market.label)
            if existing is None or len(market.outcomes) > len(existing.outcomes):
                merged[market.label] = market
        markets = list(merged.values())
        roster = self._extract_roster_from_markets(markets)
        return {
            "url": event.url,
            "event_id": event.event_id,
            "name": event.name,
            "home_team": event.home_team,
            "away_team": event.away_team,
            "start_date": event.start_date,
            "competition": event.competition,
            "roster": roster,
            "market_count": len(markets),
            "markets": [
                {"label": market.label, "outcomes": [(o.label, o.odds) for o in market.outcomes]}
                for market in markets
            ],
        }

    @staticmethod
    def _extract_roster_from_markets(markets: list[UnibetMarket]) -> list[str]:
        garbage = {"joueur", "equipe", "player"}
        roster: list[str] = []
        for market in markets:
            label = market.label
            for pattern in (
                r"plus / moins points\s*-\s*(.+?)\s*-\s*match",
                r"plus / moins rebonds\s*-\s*(.+?)\s*-\s*match",
                r"plus / moins passes[^-]*-\s*(.+?)\s*-\s*match",
                r"paniers 3 pts[^-]*-\s*(.+?)\s*-\s*match",
                r"\+/- paniers 3 pts[^-]*-\s*(.+?)\s*-\s*match",
            ):
                match = re.search(pattern, label, flags=re.I)
                if match:
                    name = match.group(1).strip()
                    if name.lower() not in garbage:
                        roster.append(name)
            for outcome in market.outcomes:
                tier = re.match(r"(.+?)\s+\d+\+$", outcome.label.strip())
                if tier:
                    name = tier.group(1).strip()
                    if name.lower() not in garbage:
                        roster.append(name)
        return sorted({name for name in roster if name})
