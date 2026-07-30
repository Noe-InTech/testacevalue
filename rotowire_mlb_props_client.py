"""Client RotoWire MLB props — extraction Runs Scored DraftKings."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests


ROTOWIRE_MLB_PLAYER_PROPS_URL = "https://www.rotowire.com/betting/mlb/player-props.php?book=draftkings"

MLB_TEAM_ABBR_TO_NAME = {
    "ARI": "Arizona Diamondbacks",
    "ATL": "Atlanta Braves",
    "BAL": "Baltimore Orioles",
    "BOS": "Boston Red Sox",
    "CHC": "Chicago Cubs",
    "CWS": "Chicago White Sox",
    "CIN": "Cincinnati Reds",
    "CLE": "Cleveland Guardians",
    "COL": "Colorado Rockies",
    "DET": "Detroit Tigers",
    "HOU": "Houston Astros",
    "KC": "Kansas City Royals",
    "KCR": "Kansas City Royals",
    "LAA": "Los Angeles Angels",
    "LAD": "Los Angeles Dodgers",
    "MIA": "Miami Marlins",
    "MIL": "Milwaukee Brewers",
    "MIN": "Minnesota Twins",
    "NYM": "New York Mets",
    "NYY": "New York Yankees",
    "ATH": "Athletics",
    "OAK": "Athletics",
    "PHI": "Philadelphia Phillies",
    "PIT": "Pittsburgh Pirates",
    "SD": "San Diego Padres",
    "SDP": "San Diego Padres",
    "SF": "San Francisco Giants",
    "SFG": "San Francisco Giants",
    "SEA": "Seattle Mariners",
    "STL": "St. Louis Cardinals",
    "TB": "Tampa Bay Rays",
    "TBR": "Tampa Bay Rays",
    "TEX": "Texas Rangers",
    "TOR": "Toronto Blue Jays",
    "WSH": "Washington Nationals",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_balanced_json_array(blob: str, start_idx: int) -> str:
    depth = 0
    in_string = False
    escape = False
    for idx in range(start_idx, len(blob)):
        char = blob[idx]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return blob[start_idx : idx + 1]
    raise ValueError("RotoWire data array not closed")


@dataclass(frozen=True)
class RotoWireRunsRow:
    player_name: str
    home_team: str
    away_team: str
    over_line: float
    over_american: int | None
    under_american: int | None
    market_label: str = "Runs Scored"
    source_label: str = "RotoWire"
    bookmaker: str = "DraftKings"


class RotoWireMlbPropsClient:
    def __init__(self, *, timeout: float = 20.0) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def fetch_draftkings_runs_rows(self) -> tuple[list[RotoWireRunsRow], str]:
        html = self.session.get(ROTOWIRE_MLB_PLAYER_PROPS_URL, timeout=self.timeout).text
        fetched_at = utc_now()
        return self.extract_draftkings_runs_rows_from_html(html), fetched_at

    def extract_draftkings_runs_rows_from_html(self, html: str) -> list[RotoWireRunsRow]:
        token = 'const prop = "runs"'
        start = html.find(token)
        if start == -1:
            return []
        data_marker = "data: ["
        data_start = html.find(data_marker, start)
        if data_start == -1:
            return []
        array_start = data_start + len("data: ")
        payload = json.loads(_extract_balanced_json_array(html, array_start))
        rows: list[RotoWireRunsRow] = []
        for item in payload:
            parsed = self._parse_runs_row(item)
            if parsed is not None:
                rows.append(parsed)
        return rows

    def _parse_runs_row(self, item: dict[str, Any]) -> RotoWireRunsRow | None:
        player_name = str(item.get("name") or "").strip()
        team = str(item.get("team") or "").strip().upper()
        opp = str(item.get("opp") or "").strip().upper()
        line = self._parse_line(item.get("draftkings_runs"))
        over = self._parse_american(item.get("draftkings_runsOver"))
        under = self._parse_american(item.get("draftkings_runsUnder"))
        if not player_name or not team or not opp or line is None or over is None or under is None:
            return None
        home_team, away_team = self._resolve_matchup(team, opp)
        if not home_team or not away_team:
            return None
        return RotoWireRunsRow(
            player_name=player_name,
            home_team=home_team,
            away_team=away_team,
            over_line=line,
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

    @staticmethod
    def _resolve_matchup(team_abbr: str, opp_label: str) -> tuple[str, str]:
        opponent_abbr = opp_label.replace("VS ", "").replace("@", "").strip()
        team_name = MLB_TEAM_ABBR_TO_NAME.get(team_abbr, "")
        opponent_name = MLB_TEAM_ABBR_TO_NAME.get(opponent_abbr, "")
        if not team_name or not opponent_name:
            return "", ""
        if opp_label.startswith("@"):
            return opponent_name, team_name
        return team_name, opponent_name
