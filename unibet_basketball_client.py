"""Client Unibet FR — basketball / WNBA."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from basketball_constants import UNIBET_BASKETBALL_LISTING_PATH
from unibet_client import UnibetClient, UnibetMarket, UnibetOutcome


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
        html = self.get_tennis_listing_html(UNIBET_BASKETBALL_LISTING_PATH)
        events: dict[str, UnibetBasketballEvent] = {}
        for match in re.finditer(
            r'href="(/paris-basketball/usa/nba/\d+/[^"]+)"',
            html,
            flags=re.I,
        ):
            path = match.group(1)
            slug = path.rsplit("/", 1)[-1]
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
        return sorted(events.values(), key=lambda item: item.name)

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
        merged: dict[str, UnibetMarket] = {}

        for match in re.finditer(r'"marketDesc":"([^"]+)"', html):
            market_desc = match.group(1).strip()
            lower = self._strip_html(market_desc).lower()
            if not self._is_player_market_desc(lower):
                continue
            chunk = html[match.start() : match.start() + 2200]
            outcomes = self._parse_ou_outcomes(chunk)
            if outcomes:
                existing = merged.get(market_desc)
                if existing is None or len(outcomes) > len(existing.outcomes):
                    merged[market_desc] = UnibetMarket(label=market_desc, outcomes=tuple(outcomes))
                continue

            performance_outcomes = self._parse_performance_outcomes(chunk)
            if performance_outcomes:
                existing = merged.get(market_desc)
                if existing is None or len(performance_outcomes) > len(existing.outcomes):
                    merged[market_desc] = UnibetMarket(
                        label=market_desc,
                        outcomes=tuple(performance_outcomes),
                    )

        return list(merged.values())

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
        for match in re.finditer(
            r'"description":"(Plus|Moins) ([\d.]+)"[^}]*?"price":"([^"]+)"',
            chunk,
            flags=re.I,
        ):
            side = match.group(1).capitalize()
            line = match.group(2)
            label = f"{side} {line}"
            if label in seen:
                continue
            odds = self._parse_decimal_odds(match.group(3))
            if odds is None:
                continue
            seen.add(label)
            outcomes.append(UnibetOutcome(label=label, odds=odds))
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
