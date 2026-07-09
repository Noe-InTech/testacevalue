"""Client de découverte SSR pour Betclic France."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable

import requests

from betclic_grpc import (
    extract_payload_from_frames,
    fetch_match_grpc_frames,
    protobuf_to_ssr_payload,
)

BASE_URL = "https://www.betclic.fr"
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Referer": "https://www.google.com/",
}


@dataclass(frozen=True)
class BetclicCompetition:
    competition_id: str
    competition_name: str
    sport_code: str
    country_code: str


@dataclass(frozen=True)
class BetclicMatchLink:
    url: str
    match_id: str
    slug: str


@dataclass(frozen=True)
class BetclicOutcome:
    label: str
    odds: float | None


@dataclass(frozen=True)
class BetclicMarket:
    label: str
    outcomes: tuple[BetclicOutcome, ...]


class BetclicClient:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def get_page_html(self, path: str = "/tennis-stennis") -> str:
        response = self.session.get(self._url(path), timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"Betclic page {response.status_code}: {response.text[:200]}")
        return response.text

    def extract_ng_state(self, html: str) -> dict[str, Any]:
        match = re.search(
            r'<script id="ng-state" type="application/json">(.*?)</script>',
            html,
            flags=re.S,
        )
        if not match:
            return {}
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return {}

    def extract_sports_payloads(self, ng_state: dict[str, Any]) -> list[dict[str, Any]]:
        payloads = []
        for value in ng_state.values():
            if not isinstance(value, dict):
                continue
            response = value.get("response") or {}
            payload = response.get("payload")
            if isinstance(payload, dict) and "sports" in payload:
                payloads.append(payload)
        return payloads

    def list_tennis_competitions(self, path: str = "/tennis-stennis") -> list[BetclicCompetition]:
        html = self.get_page_html(path)
        ng_state = self.extract_ng_state(html)
        competitions: dict[str, BetclicCompetition] = {}
        for payload in self.extract_sports_payloads(ng_state):
            for sport in payload.get("sports", []):
                if sport.get("sportCode") != "tennis":
                    continue
                for country in sport.get("countries", []):
                    for competition in country.get("competitions", []):
                        item = BetclicCompetition(
                            competition_id=str(competition.get("competitionId", "")),
                            competition_name=str(competition.get("competitionName", "")),
                            sport_code=str(competition.get("sportCode", "")),
                            country_code=str(competition.get("countryCode", "")),
                        )
                        if item.competition_id:
                            competitions[item.competition_id] = item
                for category in sport.get("categories", []):
                    for competition in category.get("competitions", []):
                        item = BetclicCompetition(
                            competition_id=str(competition.get("competitionId", "")),
                            competition_name=str(competition.get("competitionName", "")),
                            sport_code=str(competition.get("sportCode", "")),
                            country_code=str(competition.get("countryCode", "")),
                        )
                        if item.competition_id:
                            competitions[item.competition_id] = item
                for competition in sport.get("topsAndPinned", []):
                    if competition.get("sportCode") != "tennis":
                        continue
                    item = BetclicCompetition(
                        competition_id=str(competition.get("competitionId", "")),
                        competition_name=str(competition.get("competitionName", "")),
                        sport_code=str(competition.get("sportCode", "")),
                        country_code=str(competition.get("countryCode", "")),
                    )
                    if item.competition_id:
                        competitions[item.competition_id] = item
        return sorted(
            competitions.values(),
            key=lambda item: (item.country_code, item.competition_name),
        )

    def list_tennis_match_links(self, path: str = "/tennis-stennis") -> list[BetclicMatchLink]:
        html = self.get_page_html(path)
        links: dict[str, BetclicMatchLink] = {}
        for href in re.findall(r'href="(/tennis-stennis/[^"]+)"', html):
            parts = [part for part in href.split("/") if part]
            if len(parts) < 3:
                continue
            lower = href.lower()
            if any(token in lower for token in ("doubles", "d-mixte", "double")):
                continue
            match = re.search(r"-m(\d+)$", href)
            if not match:
                continue
            match_id = match.group(1)
            slug = href.rsplit("/", 1)[-1]
            slug_body = slug.rsplit("-m", 1)[0]
            if re.search(r"\d{4}$", slug_body):
                continue
            links[match_id] = BetclicMatchLink(
                url=f"{self.base_url}{href}",
                match_id=match_id,
                slug=slug,
            )
        return sorted(links.values(), key=lambda item: item.url)

    def find_match_grpc_payload(self, ng_state: dict[str, Any]) -> dict[str, Any]:
        best_payload: dict[str, Any] = {}
        best_score = -1
        for value in ng_state.values():
            if not isinstance(value, dict):
                continue
            payload = (value.get("response") or {}).get("payload")
            if not isinstance(payload, dict):
                continue
            match = payload.get("match")
            if not isinstance(match, dict):
                continue
            score = int(match.get("openMarketCount") or 0)
            sub_categories = match.get("subCategories") or []
            for sub in sub_categories:
                score += len(sub.get("markets") or [])
            if score > best_score:
                best_score = score
                best_payload = payload
        return best_payload

    def get_match_payload(self, match_url: str) -> dict[str, Any]:
        response = self.session.get(match_url, timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"Betclic match page {response.status_code}: {response.text[:200]}")
        ng_state = self.extract_ng_state(response.text)
        payload = self.find_match_grpc_payload(ng_state)
        if not payload:
            raise RuntimeError(f"Betclic match payload introuvable pour {match_url}")
        return payload

    def _grpc_context(self, match_url: str) -> tuple[dict[str, Any], str, str, str]:
        response = self.session.get(match_url, timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"Betclic match page {response.status_code}: {response.text[:200]}")
        ng_state = self.extract_ng_state(response.text)
        app_context = ng_state.get("app-context") or {}
        config = app_context.get("appSettings") or {}
        grpc_url = str(config.get("grpcOfferingUrl", "")).strip()
        token = self.session.cookies.get("BC-TOKEN", "")
        if not grpc_url or not token:
            raise RuntimeError("Betclic gRPC context incomplet (grpcOfferingUrl / BC-TOKEN)")
        return ng_state, grpc_url, token, match_url

    def fetch_grpc_match_payload(
        self,
        match_url: str,
        category_id: str | None = None,
    ) -> dict[str, Any] | None:
        try:
            _ng_state, grpc_url, token, referer = self._grpc_context(match_url)
            payload = self.find_match_grpc_payload(_ng_state)
            match_id = str((payload.get("match") or {}).get("matchId", ""))
            if not match_id:
                return None
            frames = fetch_match_grpc_frames(
                self.session,
                grpc_offering_url=grpc_url,
                match_id=match_id,
                referer=referer,
                token=token,
                category_id=category_id,
            )
            decoded = extract_payload_from_frames(frames)
            if not decoded:
                return None
            return protobuf_to_ssr_payload(decoded)
        except Exception:
            return None

    def get_full_match_payload(
        self,
        match_url: str,
        *,
        grpc_categories: tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        base_payload = self.get_match_payload(match_url)
        match = base_payload.get("match") or {}
        category_ids = [
            str(category.get("id", ""))
            for category in (match.get("categories") or [])
            if category.get("id")
        ]
        if not category_ids:
            category_ids = [""]

        merged_markets: dict[str, dict[str, Any]] = {}
        grpc_category_hits = 0

        def absorb_payload(payload: dict[str, Any] | None, *, from_grpc: bool = False) -> None:
            nonlocal grpc_category_hits
            if not payload:
                return
            if from_grpc:
                grpc_category_hits += 1
            for market in self.extract_markets_from_match_payload(payload):
                key = market.label.strip().lower()
                existing = merged_markets.get(key)
                if existing and len(existing["outcomes"]) >= len(market.outcomes):
                    continue
                merged_markets[key] = {
                    "label": market.label,
                    "outcomes": [(item.label, item.odds) for item in market.outcomes],
                }

        absorb_payload(base_payload)
        if grpc_categories is not None:
            ordered_categories = [cid for cid in grpc_categories if cid in category_ids]
        else:
            priority_categories = ["ca_ten_ptss", "ca_ten_main", "ca_ten_sets"]
            ordered_categories = [cid for cid in priority_categories if cid in category_ids]
            ordered_categories.extend(cid for cid in category_ids if cid not in priority_categories)
        for category_id in ordered_categories:
            if not category_id:
                continue
            absorb_payload(
                self.fetch_grpc_match_payload(match_url, category_id=category_id),
                from_grpc=True,
            )

        if merged_markets:
            synthetic_sub_categories = [
                {
                    "markets": [
                        {
                            "id": f"grpc-{index}",
                            "betslipName": market["label"],
                            "name": market["label"],
                            "mainSelections": [
                                {
                                    "name": label,
                                    "betslipName": label,
                                    "odds": odds,
                                    "status": 1,
                                    "betslipMarketId": f"grpc-{index}",
                                }
                                for label, odds in market["outcomes"]
                                if odds is not None
                            ],
                        }
                        for index, market in enumerate(merged_markets.values())
                    ]
                }
            ]
            match = dict(match)
            existing = match.get("subCategories") or []
            if isinstance(existing, list):
                match["subCategories"] = existing + synthetic_sub_categories
            else:
                match["subCategories"] = synthetic_sub_categories
            base_payload["match"] = match
            base_payload["grpc_category_hits"] = grpc_category_hits
            base_payload["grpc_market_count"] = len(merged_markets)
        return base_payload

    @staticmethod
    def _iter_selection_nodes(node: Any) -> Iterable[dict[str, Any]]:
        if isinstance(node, dict):
            if "betslipMarketId" in node and "name" in node:
                yield node
            if "selection" in node and isinstance(node["selection"], dict):
                yield node["selection"]
            selection_oneof = node.get("selectionOneof")
            if isinstance(selection_oneof, dict):
                selection = selection_oneof.get("selection")
                if isinstance(selection, dict):
                    yield selection
            for value in node.values():
                yield from BetclicClient._iter_selection_nodes(value)
        elif isinstance(node, list):
            for item in node:
                yield from BetclicClient._iter_selection_nodes(item)

    @staticmethod
    def _collect_market_outcomes(market: dict[str, Any]) -> list[BetclicOutcome]:
        outcomes: list[BetclicOutcome] = []
        seen: set[str] = set()
        for selection in BetclicClient._iter_selection_nodes(market):
            if selection.get("status") not in (None, 1):
                continue
            label = str(selection.get("name", "")).strip()
            if not label or label in seen:
                continue
            odds = selection.get("odds")
            try:
                parsed_odds = float(odds) if odds is not None else None
            except (TypeError, ValueError):
                parsed_odds = None
            seen.add(label)
            outcomes.append(BetclicOutcome(label=label, odds=parsed_odds))
        return outcomes

    def extract_markets_from_match_payload(self, payload: dict[str, Any]) -> list[BetclicMarket]:
        match = payload.get("match") or {}
        markets: list[BetclicMarket] = []
        seen_ids: set[str] = set()

        def add_market(market: dict[str, Any], label_override: str | None = None) -> None:
            if not isinstance(market, dict):
                return
            label = (label_override or market.get("betslipName") or market.get("name") or "").strip()
            market_id = str(market.get("id", ""))
            dedupe_key = f"{market_id}|{label}"
            if market_id and dedupe_key in seen_ids:
                return
            outcomes = tuple(self._collect_market_outcomes(market))
            if not label or not outcomes:
                return
            if market_id:
                seen_ids.add(dedupe_key)
            markets.append(BetclicMarket(label=label, outcomes=outcomes))

        def walk_subcategories(nodes: Any) -> None:
            if isinstance(nodes, dict):
                nodes = list(nodes.values())
            if not isinstance(nodes, list):
                return
            for sub_category in nodes:
                if isinstance(sub_category, list):
                    walk_subcategories(sub_category)
                    continue
                if not isinstance(sub_category, dict):
                    continue
                for market in sub_category.get("markets") or []:
                    add_market(market)
                    for grouped in market.get("groupMarkets") or []:
                        grouped_label = str(grouped.get("betslipName") or grouped.get("name") or "").strip()
                        add_market(grouped, grouped_label or None)
                if isinstance(sub_category.get("3"), list):
                    for market in sub_category.get("3") or []:
                        add_market(market)

        walk_subcategories(match.get("subCategories") or [])

        for market in match.get("markets") or []:
            add_market(market)
            for grouped in market.get("groupMarkets") or []:
                grouped_label = str(grouped.get("betslipName") or grouped.get("name") or "").strip()
                add_market(grouped, grouped_label or None)

        return markets

    def get_event_markets(self, match_url: str) -> list[BetclicMarket]:
        payload = self.get_match_payload(match_url)
        return self.extract_markets_from_match_payload(payload)

    def build_event_payload(
        self,
        match_url: str,
        *,
        grpc_categories: tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        payload = self.get_full_match_payload(match_url, grpc_categories=grpc_categories)
        match = payload.get("match") or {}
        contestants = match.get("contestants") or []
        home = contestants[0].get("name", "") if len(contestants) > 0 else ""
        away = contestants[1].get("name", "") if len(contestants) > 1 else ""
        markets = self.extract_markets_from_match_payload(payload)
        return {
            "url": match_url,
            "match_id": str(match.get("matchId", "")),
            "name": str(match.get("name", "")),
            "home_player": home,
            "away_player": away,
            "start_date": match.get("matchDateUtc", ""),
            "competition": ((match.get("competition") or {}).get("name", "")),
            "open_market_count": int(match.get("openMarketCount") or 0),
            "ssr_market_count": len(markets),
            "grpc_market_count": payload.get("grpc_market_count", 0),
            "grpc_category_hits": payload.get("grpc_category_hits", 0),
            "categories": [
                {"id": str(category.get("id", "")), "name": str(category.get("name", ""))}
                for category in (match.get("categories") or [])
            ],
            "markets": [
                {"label": market.label, "outcomes": [(o.label, o.odds) for o in market.outcomes]}
                for market in markets
            ],
        }
