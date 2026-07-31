"""Client RotoWire basketball props — DraftKings O/U (WNBA / NBA)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from rotowire_mlb_props_client import _extract_balanced_json_array

ROTOWIRE_WNBA_PLAYER_PROPS_URL = (
    "https://www.rotowire.com/betting/wnba/player-props.php?book=draftkings"
)
ROTOWIRE_NBA_PLAYER_PROPS_URL = (
    "https://www.rotowire.com/betting/nba/player-props.php?book=draftkings"
)

PROP_SPECS: tuple[tuple[str, str, str], ...] = (
    ("pts", "points_player", "Points"),
    ("reb", "rebounds_player", "Rebounds"),
    ("ast", "assists_player", "Assists"),
    ("threes", "threes_made_player", "Made Threes"),
)

WNBA_TEAM_ABBR_TO_NAME = {
    "ATL": "Atlanta Dream",
    "CHI": "Chicago Sky",
    "CON": "Connecticut Sun",
    "CONN": "Connecticut Sun",
    "DAL": "Dallas Wings",
    "GS": "Golden State Valkyries",
    "GSV": "Golden State Valkyries",
    "IND": "Indiana Fever",
    "LA": "Los Angeles Sparks",
    "LAS": "Los Angeles Sparks",
    "LVA": "Las Vegas Aces",
    "LV": "Las Vegas Aces",
    "MIN": "Minnesota Lynx",
    "NY": "New York Liberty",
    "NYL": "New York Liberty",
    "PHX": "Phoenix Mercury",
    "PHO": "Phoenix Mercury",
    "POR": "Portland Fire",
    "SEA": "Seattle Storm",
    "TOR": "Toronto Tempo",
    "WAS": "Washington Mystics",
    "WSH": "Washington Mystics",
}

NBA_TEAM_ABBR_TO_NAME = {
    "ATL": "Atlanta Hawks",
    "BOS": "Boston Celtics",
    "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets",
    "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks",
    "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons",
    "GS": "Golden State Warriors",
    "GSW": "Golden State Warriors",
    "HOU": "Houston Rockets",
    "IND": "Indiana Pacers",
    "LAC": "LA Clippers",
    "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves",
    "NO": "New Orleans Pelicans",
    "NOP": "New Orleans Pelicans",
    "NY": "New York Knicks",
    "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",
    "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers",
    "SAC": "Sacramento Kings",
    "SA": "San Antonio Spurs",
    "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors",
    "UTA": "Utah Jazz",
    "WAS": "Washington Wizards",
    "WSH": "Washington Wizards",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RotoWireBasketballPropRow:
    player_name: str
    home_team: str
    away_team: str
    market_family: str
    market_label: str
    line: float
    over_american: int
    under_american: int
    source_label: str = "RotoWire"
    bookmaker: str = "DraftKings"


class RotoWireBasketballPropsClient:
    def __init__(self, league: str = "wnba", *, timeout: float = 20.0) -> None:
        self.league = str(league or "wnba").strip().lower()
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    @property
    def props_url(self) -> str:
        if self.league == "nba":
            return ROTOWIRE_NBA_PLAYER_PROPS_URL
        return ROTOWIRE_WNBA_PLAYER_PROPS_URL

    @property
    def team_abbr_map(self) -> dict[str, str]:
        if self.league == "nba":
            return NBA_TEAM_ABBR_TO_NAME
        return WNBA_TEAM_ABBR_TO_NAME

    def fetch_draftkings_prop_rows(self) -> tuple[list[RotoWireBasketballPropRow], str]:
        html = self.session.get(self.props_url, timeout=self.timeout).text
        fetched_at = utc_now()
        return self.extract_draftkings_prop_rows_from_html(html), fetched_at

    def extract_draftkings_prop_rows_from_html(self, html: str) -> list[RotoWireBasketballPropRow]:
        rows: list[RotoWireBasketballPropRow] = []
        for prop_token, family, label in PROP_SPECS:
            token = f'const prop = "{prop_token}"'
            start = html.find(token)
            if start == -1:
                continue
            data_start = html.find("data: [", start)
            if data_start == -1:
                continue
            payload = json.loads(_extract_balanced_json_array(html, data_start + len("data: ")))
            for item in payload:
                parsed = self._parse_prop_row(item, prop_token=prop_token, family=family, label=label)
                if parsed is not None:
                    rows.append(parsed)
        return rows

    def _parse_prop_row(
        self,
        item: dict[str, Any],
        *,
        prop_token: str,
        family: str,
        label: str,
    ) -> RotoWireBasketballPropRow | None:
        player_name = str(item.get("name") or "").strip()
        team = str(item.get("team") or "").strip().upper()
        opp = str(item.get("opp") or "").strip().upper()
        line = self._parse_line(item.get(f"draftkings_{prop_token}"))
        over = self._parse_american(item.get(f"draftkings_{prop_token}Over"))
        under = self._parse_american(item.get(f"draftkings_{prop_token}Under"))
        if not player_name or not team or not opp or line is None or over is None or under is None:
            return None
        home_team, away_team = self._resolve_matchup(team, opp)
        if not home_team or not away_team:
            return None
        return RotoWireBasketballPropRow(
            player_name=player_name,
            home_team=home_team,
            away_team=away_team,
            market_family=family,
            market_label=label,
            line=line,
            over_american=over,
            under_american=under,
        )

    @staticmethod
    def _parse_line(value: Any) -> float | None:
        text = str(value or "").strip()
        if not text:
            return None
        match = re.search(r"(-?\d+(?:\.\d+)?)", text.replace(",", "."))
        if not match:
            return None
        return float(match.group(1))

    @staticmethod
    def _parse_american(value: Any) -> int | None:
        text = str(value or "").strip()
        if not text:
            return None
        text = text.replace("−", "-")
        try:
            return int(float(text))
        except ValueError:
            return None

    def _resolve_matchup(self, team_abbr: str, opp_label: str) -> tuple[str, str]:
        opponent_abbr = opp_label.replace("VS ", "").replace("@", "").strip()
        team_name = self.team_abbr_map.get(team_abbr, "")
        opponent_name = self.team_abbr_map.get(opponent_abbr, "")
        if not team_name or not opponent_name:
            return "", ""
        if opp_label.startswith("@"):
            return opponent_name, team_name
        return team_name, opponent_name
