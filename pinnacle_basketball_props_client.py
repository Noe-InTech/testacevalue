"""Props joueurs basket Pinnacle (API invitée du site), NBA et WNBA."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pinnacle_guest_client import PinnacleGuestClient

BASKETBALL_SPORT_ID = 4

_PROP_DESCRIPTION = re.compile(
    r"^(?P<player>.+?) Total (?P<stat>Points|Rebounds|Assists|Threes Made)$",
    re.IGNORECASE,
)

_STAT_TO_FAMILY = {
    "points": ("points_player", "Points"),
    "rebounds": ("rebounds_player", "Rebounds"),
    "assists": ("assists_player", "Assists"),
    "threes made": ("threes_made_player", "Made Threes"),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PinnacleBasketballPropRow:
    player_name: str
    home_team: str
    away_team: str
    market_family: str
    market_label: str
    line: float
    over_american: int
    under_american: int
    source_label: str = "Pinnacle"
    bookmaker: str = "Pinnacle"


class PinnacleBasketballPropsClient:
    def __init__(self, league: str = "nba") -> None:
        self.league = "nba" if str(league or "").strip().lower() == "nba" else "wnba"
        self._api = PinnacleGuestClient()

    def fetch_prop_rows(self) -> tuple[list[PinnacleBasketballPropRow], str]:
        league_id = self._resolve_league_id()
        matchups = self._api.get_league_matchups(league_id)
        markets = self._api.get_league_markets(league_id)
        fetched_at = utc_now()
        return self.extract_prop_rows(matchups, markets), fetched_at

    def _resolve_league_id(self) -> int:
        target = self.league
        for league in self._api.get_leagues(BASKETBALL_SPORT_ID):
            name = str(league.get("name") or "").strip().lower()
            if name == target:
                return int(league["id"])
        raise RuntimeError(f"Ligue Pinnacle {target.upper()} introuvable")

    @classmethod
    def extract_prop_rows(
        cls,
        matchups: list[dict[str, Any]],
        markets: list[dict[str, Any]],
    ) -> list[PinnacleBasketballPropRow]:
        by_id = {int(item["id"]): item for item in matchups if item.get("id") is not None}
        markets_by_matchup: dict[int, list[dict[str, Any]]] = {}
        for market in markets:
            matchup_id = market.get("matchupId")
            if matchup_id is None:
                continue
            markets_by_matchup.setdefault(int(matchup_id), []).append(market)

        rows: list[PinnacleBasketballPropRow] = []
        for matchup in matchups:
            if str((matchup.get("special") or {}).get("category") or "") != "Player Props":
                continue
            if matchup.get("isLive"):
                continue
            parsed = _parse_description(str((matchup.get("special") or {}).get("description") or ""))
            if parsed is None:
                continue
            player_name, family, label = parsed
            home_team, away_team = _parent_teams(matchup, by_id)
            if not home_team or not away_team:
                continue
            sides = _participant_sides(matchup)
            for market in markets_by_matchup.get(int(matchup["id"]), []):
                row = _row_from_market(
                    market,
                    player_name=player_name,
                    home_team=home_team,
                    away_team=away_team,
                    family=family,
                    label=label,
                    sides=sides,
                )
                if row is not None:
                    rows.append(row)
        return rows


def _parse_description(description: str) -> tuple[str, str, str] | None:
    match = _PROP_DESCRIPTION.match(description.strip())
    if not match:
        return None
    player_name = match.group("player").strip()
    stat = match.group("stat").strip().lower()
    mapped = _STAT_TO_FAMILY.get(stat)
    if not player_name or mapped is None:
        return None
    family, label = mapped
    return player_name, family, label


def _parent_teams(
    matchup: dict[str, Any],
    by_id: dict[int, dict[str, Any]],
) -> tuple[str, str]:
    parent = matchup.get("parent")
    if not isinstance(parent, dict):
        parent_id = matchup.get("parentId")
        parent = by_id.get(int(parent_id)) if parent_id is not None else None
    if not isinstance(parent, dict):
        return "", ""
    home = ""
    away = ""
    for participant in parent.get("participants") or []:
        alignment = str(participant.get("alignment") or "")
        name = str(participant.get("name") or "").strip()
        if alignment == "home":
            home = name
        elif alignment == "away":
            away = name
    return home, away


def _participant_sides(matchup: dict[str, Any]) -> dict[int, str]:
    sides: dict[int, str] = {}
    for participant in matchup.get("participants") or []:
        participant_id = participant.get("id")
        name = str(participant.get("name") or "").strip().lower()
        if participant_id is None:
            continue
        if name == "over":
            sides[int(participant_id)] = "Over"
        elif name == "under":
            sides[int(participant_id)] = "Under"
    return sides


def _row_from_market(
    market: dict[str, Any],
    *,
    player_name: str,
    home_team: str,
    away_team: str,
    family: str,
    label: str,
    sides: dict[int, str],
) -> PinnacleBasketballPropRow | None:
    if market.get("isAlternate") or str(market.get("type") or "") != "total":
        return None
    if int(market.get("period") or 0) != 0:
        return None
    over_price: int | None = None
    under_price: int | None = None
    line: float | None = None
    for price in market.get("prices") or []:
        participant_id = price.get("participantId")
        side = sides.get(int(participant_id)) if participant_id is not None else None
        if side not in {"Over", "Under"}:
            continue
        american = price.get("price")
        points = price.get("points")
        if american in (None, 0) or points is None:
            continue
        try:
            american_int = int(american)
            points_float = float(points)
        except (TypeError, ValueError):
            continue
        if line is None:
            line = points_float
        elif line != points_float:
            return None
        if side == "Over":
            over_price = american_int
        else:
            under_price = american_int
    if line is None or over_price is None or under_price is None:
        return None
    return PinnacleBasketballPropRow(
        player_name=player_name,
        home_team=home_team,
        away_team=away_team,
        market_family=family,
        market_label=label,
        line=line,
        over_american=over_price,
        under_american=under_price,
    )
