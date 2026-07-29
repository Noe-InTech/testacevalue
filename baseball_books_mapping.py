"""Normalisation marchés baseball — books FR (Unibet / Winamax)."""

from __future__ import annotations

import re
from typing import Iterable

from baseball_market_mapping import (
    build_f5_h2h_key,
    build_f5_run_line_key,
    build_f5_runs_total_key,
    build_h2h_key,
    build_hr_player_key,
    build_inning1_result_key,
    build_inning1_runs_total_key,
    build_run_line_key,
    build_runs_player_key,
    build_runs_team_key,
    build_runs_total_key,
    build_strikeouts_pitcher_key,
    parse_signed_line,
    resolve_roster_player,
    resolve_team_side,
    strip_accents,
    team_token,
)
from tennis_books_mapping import (
    NormalizedMarket,
    build_market,
    format_line,
    normalize_ou_label,
    parse_french_number,
)
from tennis_market_mapping import players_match


def is_baseball_comparable_label(label: str) -> bool:
    lower = strip_accents(label)
    markers = (
        "face a face",
        "vainqueur",
        "1 n 2",
        "1n2",
        "handicap",
        "ecart de runs",
        "plus / moins",
        "nombre de runs",
        "nombre total de runs",
        "inning 1",
        "1er inning",
        "1er manche",
        "1ere manche",
        "inning 1 au inning 5",
        "first 5",
        "5 premiers innings",
        "marque",
        "marqueur de home run",
        "home run",
        "strikeout",
        "retraits sur des",
        "prolongation",
        "manche supplementaire",
        "resultat",
    )
    return any(marker in lower for marker in markers)


def _ou_map(outcomes: Iterable[tuple[str, float | None]]) -> dict[str, float]:
    result: dict[str, float] = {}
    for raw, odds in outcomes:
        if odds is None:
            continue
        side = normalize_ou_label(raw)
        if side in {"Over", "Under"}:
            result[side] = float(odds)
        else:
            lower = strip_accents(raw)
            if "plus" in lower or "over" in lower:
                result["Over"] = float(odds)
            elif "moins" in lower or "under" in lower:
                result["Under"] = float(odds)
    return result


def _team_side_map(
    outcomes: Iterable[tuple[str, float | None]],
    *,
    home_team: str,
    away_team: str,
) -> dict[str, float]:
    result: dict[str, float] = {}
    for raw, odds in outcomes:
        if odds is None:
            continue
        side = resolve_team_side(raw, home_team, away_team)
        if side:
            result[side] = float(odds)
    return result


def _extract_line_from_label(label: str) -> float | None:
    return parse_french_number(label)


def normalize_unibet_market(
    label: str,
    outcomes: list[tuple[str, float | None]],
    *,
    home_team: str,
    away_team: str,
    roster: list[str] | None = None,
) -> list[NormalizedMarket]:
    roster = roster or []
    lower = strip_accents(label)
    markets: list[NormalizedMarket] = []

    # Moneyline 2-way
    if lower.startswith("face a face - match") and "handicap" not in lower:
        item = build_market(
            build_h2h_key(),
            "h2h",
            label,
            _team_side_map(outcomes, home_team=home_team, away_team=away_team),
        )
        if item:
            markets.append(item)
        return markets

    # 1N2 regulation — keep only if no draw needed for h2h; skip for main h2h
    if lower.startswith("1 n 2 - temps reglementaire"):
        return markets

    # Run line / handicap match (possibly multiple lines in outcomes)
    if "face a face handicap" in lower and "inning 1 au inning 5" not in lower:
        by_line: dict[str, dict[str, float]] = {}
        for raw, odds in outcomes:
            if odds is None:
                continue
            line = parse_signed_line(raw)
            side = resolve_team_side(raw, home_team, away_team)
            if line is None or side not in {"home", "away"}:
                continue
            key = format_line(abs(line))
            by_line.setdefault(key, {})[side] = float(odds)
        for line_key, outcome_map in by_line.items():
            item = build_market(
                build_run_line_key(line_key),
                "run_line",
                label,
                outcome_map,
                line=line_key,
            )
            if item:
                markets.append(item)
        return markets

    # Total runs match
    if lower.startswith("plus / moins points - match") or re.match(
        r"plus / moins point\(s\)\s+[\d.,]+\s*-\s*match",
        lower,
    ):
        # Outcomes may encode multiple lines
        by_line: dict[str, dict[str, float]] = {}
        for raw, odds in outcomes:
            if odds is None:
                continue
            line = parse_french_number(raw) or _extract_line_from_label(label)
            side = normalize_ou_label(raw)
            if line is None or side not in {"Over", "Under"}:
                continue
            key = format_line(line)
            by_line.setdefault(key, {})[side] = float(odds)
        for line_key, outcome_map in by_line.items():
            item = build_market(
                build_runs_total_key(line_key),
                "runs_total",
                label,
                outcome_map,
                line=line_key,
            )
            if item:
                markets.append(item)
        return markets

    # Team totals
    team_total = re.search(
        r"plus / moins point\(s\)\s*-\s*(.+?)\s*-\s*match",
        lower,
    ) or re.search(r"plus / moins point\(s\)\s*-\s*equipe\s*-\s*match", lower)
    if "plus / moins point(s) -" in lower and "match" in lower and "inning" not in lower:
        # Explicit team in label
        team_match = re.search(
            r"plus / moins point\(s\)\s*-\s*(.+?)\s*-\s*match",
            label,
            flags=re.I,
        )
        team_name = ""
        if team_match:
            team_name = team_match.group(1).strip()
            if strip_accents(team_name) in {"equipe", "team"}:
                team_name = ""
        # Outcomes may repeat lines for both teams without names — skip ambiguous
        if team_name and (
            players_match(team_name, home_team) or players_match(team_name, away_team)
        ):
            by_line: dict[str, dict[str, float]] = {}
            for raw, odds in outcomes:
                if odds is None:
                    continue
                line = parse_french_number(raw)
                side = normalize_ou_label(raw)
                if line is None or side not in {"Over", "Under"}:
                    continue
                key = format_line(line)
                by_line.setdefault(key, {})[side] = float(odds)
            for line_key, outcome_map in by_line.items():
                item = build_market(
                    build_runs_team_key(team_name, line_key),
                    "runs_team",
                    label,
                    outcome_map,
                    player_name=team_name,
                    line=line_key,
                )
                if item:
                    markets.append(item)
            return markets

    # F5 moneyline
    if "vainqueur du inning 1 au inning 5" in lower:
        item = build_market(
            build_f5_h2h_key(),
            "f5_h2h",
            label,
            _team_side_map(outcomes, home_team=home_team, away_team=away_team),
        )
        if item:
            markets.append(item)
        return markets

    # F5 handicap
    if "face a face handicap du inning 1 au inning 5" in lower:
        by_line: dict[str, dict[str, float]] = {}
        for raw, odds in outcomes:
            if odds is None:
                continue
            line = parse_signed_line(raw)
            side = resolve_team_side(raw, home_team, away_team)
            if line is None or side not in {"home", "away"}:
                continue
            key = format_line(abs(line))
            by_line.setdefault(key, {})[side] = float(odds)
        for line_key, outcome_map in by_line.items():
            item = build_market(
                build_f5_run_line_key(line_key),
                "f5_run_line",
                label,
                outcome_map,
                line=line_key,
            )
            if item:
                markets.append(item)
        return markets

    # F5 totals
    if "plus / moins points du inning 1 au inning 5" in lower and "equipe" not in lower:
        by_line: dict[str, dict[str, float]] = {}
        for raw, odds in outcomes:
            if odds is None:
                continue
            line = parse_french_number(raw)
            side = normalize_ou_label(raw)
            if line is None or side not in {"Over", "Under"}:
                continue
            key = format_line(line)
            by_line.setdefault(key, {})[side] = float(odds)
        for line_key, outcome_map in by_line.items():
            item = build_market(
                build_f5_runs_total_key(line_key),
                "f5_runs_total",
                label,
                outcome_map,
                line=line_key,
            )
            if item:
                markets.append(item)
        return markets

    # 1st inning result
    if lower in {"vainqueur - 1er inning", "1 n 2 - 1er inning"} or lower.startswith(
        "1 n 2 - 1er inning"
    ):
        item = build_market(
            build_inning1_result_key(),
            "inning1_result",
            label,
            _team_side_map(outcomes, home_team=home_team, away_team=away_team),
        )
        if item:
            markets.append(item)
        return markets

    return markets


def normalize_winamax_market(
    label: str,
    outcomes: list[tuple[str, float | None]],
    *,
    home_team: str,
    away_team: str,
    roster: list[str] | None = None,
) -> list[NormalizedMarket]:
    roster = roster or []
    lower = strip_accents(label)
    # Strip trailing "(line)" appended by winamax client
    base_label = re.sub(r"\s*\([\d.,]+\)\s*$", "", label).strip()
    lower_base = strip_accents(base_label)
    markets: list[NormalizedMarket] = []

    if lower_base == "vainqueur":
        item = build_market(
            build_h2h_key(),
            "h2h",
            label,
            _team_side_map(outcomes, home_team=home_team, away_team=away_team),
        )
        if item:
            markets.append(item)
        return markets

    if "ecart de runs" in lower_base or "handicap" in lower_base:
        by_line: dict[str, dict[str, float]] = {}
        for raw, odds in outcomes:
            if odds is None:
                continue
            line = parse_signed_line(raw)
            side = resolve_team_side(raw, home_team, away_team)
            if line is None or side not in {"home", "away"}:
                continue
            key = format_line(abs(line))
            by_line.setdefault(key, {})[side] = float(odds)
        for line_key, outcome_map in by_line.items():
            item = build_market(
                build_run_line_key(line_key),
                "run_line",
                label,
                outcome_map,
                line=line_key,
            )
            if item:
                markets.append(item)
        return markets

    if lower_base == "nombre de runs" or lower_base.startswith("nombre de runs ("):
        line = _extract_line_from_label(label)
        outcome_map = _ou_map(outcomes)
        if line is not None and outcome_map:
            item = build_market(
                build_runs_total_key(line),
                "runs_total",
                label,
                outcome_map,
                line=format_line(line),
            )
            if item:
                markets.append(item)
        return markets

    team_total = re.match(r"nombre de runs de (.+)$", lower_base)
    if team_total:
        team_name = base_label[len("Nombre de runs de ") :].strip() if "Nombre de runs de " in base_label else team_total.group(1)
        # Prefer original casing from outcomes/home/away
        if players_match(team_name, home_team):
            team_name = home_team
        elif players_match(team_name, away_team):
            team_name = away_team
        line = _extract_line_from_label(label)
        # Also parse from outcome "Plus de 3,5"
        if line is None:
            for raw, _odds in outcomes:
                line = parse_french_number(raw)
                if line is not None:
                    break
        outcome_map = _ou_map(outcomes)
        if line is not None and outcome_map:
            item = build_market(
                build_runs_team_key(team_name, line),
                "runs_team",
                label,
                outcome_map,
                player_name=team_name,
                line=format_line(line),
            )
            if item:
                markets.append(item)
        return markets

    if lower_base in {"1er manche - resultat", "1ere manche - resultat"}:
        item = build_market(
            build_inning1_result_key(),
            "inning1_result",
            label,
            _team_side_map(outcomes, home_team=home_team, away_team=away_team),
        )
        if item:
            markets.append(item)
        return markets

    if lower_base.startswith("1er manche - nombre de runs") or lower_base.startswith(
        "1ere manche - nombre de runs"
    ):
        line = _extract_line_from_label(label)
        if line is None:
            for raw, _odds in outcomes:
                line = parse_french_number(raw)
                if line is not None:
                    break
        outcome_map = _ou_map(outcomes)
        if line is not None and outcome_map:
            item = build_market(
                build_inning1_runs_total_key(line),
                "inning1_runs_total",
                label,
                outcome_map,
                line=format_line(line),
            )
            if item:
                markets.append(item)
        return markets

    if lower_base == "marqueur de home run":
        for raw, odds in outcomes:
            if odds is None:
                continue
            player = resolve_roster_player(raw, roster)
            item = build_market(
                build_hr_player_key(player),
                "hr_player",
                label,
                {"Yes": float(odds)},
                player_name=player,
            )
            if item:
                markets.append(item)
        return markets

    runs_tier = re.match(r"marque\s+(\d+)\s+runs? ou plus$", lower_base)
    if runs_tier:
        threshold = int(runs_tier.group(1))
        for raw, odds in outcomes:
            if odds is None:
                continue
            player = resolve_roster_player(raw, roster)
            item = build_market(
                build_runs_player_key(player, threshold),
                "runs_player",
                label,
                {"Yes": float(odds)},
                player_name=player,
                line=str(threshold),
            )
            if item:
                markets.append(item)
        return markets

    return markets


def normalize_betclic_market(
    label: str,
    outcomes: list[tuple[str, float | None]],
    *,
    home_team: str,
    away_team: str,
    roster: list[str] | None = None,
) -> list[NormalizedMarket]:
    """Normalise les libellés Betclic baseball (proches tennis/Winamax)."""
    roster = roster or []
    raw_label = label.strip()
    base_label = re.sub(r"\s*\([\d.,]+\)\s*$", "", raw_label).strip()
    lower_base = strip_accents(base_label)
    markets: list[NormalizedMarket] = []

    if lower_base in {"vainqueur", "vainqueur du match"} or (
        lower_base.startswith("vainqueur")
        and "handicap" not in lower_base
        and "inning" not in lower_base
        and "manche" not in lower_base
    ):
        item = build_market(
            build_h2h_key(),
            "h2h",
            label,
            _team_side_map(outcomes, home_team=home_team, away_team=away_team),
        )
        if item:
            markets.append(item)
        return markets

    if (
        "handicap" in lower_base
        or "ecart de runs" in lower_base
        or "vainqueur avec handicap" in lower_base
    ) and "inning" not in lower_base and "manche" not in lower_base:
        by_line: dict[str, dict[str, float]] = {}
        for raw, odds in outcomes:
            if odds is None:
                continue
            line = parse_signed_line(raw)
            side = resolve_team_side(raw, home_team, away_team)
            if line is None or side not in {"home", "away"}:
                continue
            key = format_line(abs(line))
            by_line.setdefault(key, {})[side] = float(odds)
        for line_key, outcome_map in by_line.items():
            item = build_market(
                build_run_line_key(line_key),
                "run_line",
                label,
                outcome_map,
                line=line_key,
            )
            if item:
                markets.append(item)
        return markets

    team_total = re.match(r"nombre (?:total )?de runs de (.+)$", lower_base)
    if team_total:
        team_name = team_total.group(1).strip()
        if players_match(team_name, home_team):
            team_name = home_team
        elif players_match(team_name, away_team):
            team_name = away_team
        line = _extract_line_from_label(label)
        if line is None:
            for raw, _odds in outcomes:
                line = parse_french_number(raw)
                if line is not None:
                    break
        outcome_map = _ou_map(outcomes)
        if line is not None and outcome_map:
            item = build_market(
                build_runs_team_key(team_name, line),
                "runs_team",
                label,
                outcome_map,
                player_name=team_name,
                line=format_line(line),
            )
            if item:
                markets.append(item)
        return markets

    is_runs_total = (
        lower_base in {"nombre de runs", "nombre total de runs"}
        or lower_base.startswith("nombre de runs (")
        or lower_base.startswith("nombre total de runs (")
        or (
            "plus / moins" in lower_base
            and "run" in lower_base
            and "joueur" not in lower_base
            and "de runs de" not in lower_base
        )
    )
    if is_runs_total and "inning" not in lower_base and "manche" not in lower_base:
        by_line: dict[str, dict[str, float]] = {}
        for raw, odds in outcomes:
            if odds is None:
                continue
            line = parse_french_number(raw) or _extract_line_from_label(label)
            side = normalize_ou_label(raw)
            if side not in {"Over", "Under"}:
                mapped = _ou_map([(raw, odds)])
                side = next(iter(mapped), side)
            if line is None or side not in {"Over", "Under"}:
                continue
            key = format_line(line)
            by_line.setdefault(key, {})[side] = float(odds)
        if not by_line:
            line = _extract_line_from_label(label)
            outcome_map = _ou_map(outcomes)
            if line is not None and outcome_map:
                by_line[format_line(line)] = outcome_map
        for line_key, outcome_map in by_line.items():
            item = build_market(
                build_runs_total_key(line_key),
                "runs_total",
                label,
                outcome_map,
                line=line_key,
            )
            if item:
                markets.append(item)
        return markets

    if lower_base in {
        "vainqueur - 1er inning",
        "vainqueur - 1ere manche",
        "1er manche - resultat",
        "1ere manche - resultat",
        "resultat 1er inning",
    } or (
        ("1er inning" in lower_base or "1ere manche" in lower_base or "1er manche" in lower_base)
        and ("vainqueur" in lower_base or "resultat" in lower_base)
        and "nombre" not in lower_base
    ):
        item = build_market(
            build_inning1_result_key(),
            "inning1_result",
            label,
            _team_side_map(outcomes, home_team=home_team, away_team=away_team),
        )
        if item:
            markets.append(item)
        return markets

    if (
        "1er inning" in lower_base
        or "1ere manche" in lower_base
        or "1er manche" in lower_base
    ) and ("nombre de runs" in lower_base or "plus / moins" in lower_base):
        line = _extract_line_from_label(label)
        if line is None:
            for raw, _odds in outcomes:
                line = parse_french_number(raw)
                if line is not None:
                    break
        outcome_map = _ou_map(outcomes)
        if line is not None and outcome_map:
            item = build_market(
                build_inning1_runs_total_key(line),
                "inning1_runs_total",
                label,
                outcome_map,
                line=format_line(line),
            )
            if item:
                markets.append(item)
        return markets

    if (
        "inning 1 au inning 5" in lower_base
        or "5 premiers innings" in lower_base
        or "first 5" in lower_base
    ) and ("vainqueur" in lower_base or "resultat" in lower_base):
        item = build_market(
            build_f5_h2h_key(),
            "f5_h2h",
            label,
            _team_side_map(outcomes, home_team=home_team, away_team=away_team),
        )
        if item:
            markets.append(item)
        return markets

    if lower_base in {"marqueur de home run", "home run"} or "marquera un home run" in lower_base:
        for raw, odds in outcomes:
            if odds is None:
                continue
            player = resolve_roster_player(raw, roster)
            item = build_market(
                build_hr_player_key(player),
                "hr_player",
                label,
                {"Yes": float(odds)},
                player_name=player,
            )
            if item:
                markets.append(item)
        return markets

    runs_tier = re.match(r"marque\s+(\d+)\s+runs? ou plus$", lower_base)
    if runs_tier:
        threshold = int(runs_tier.group(1))
        for raw, odds in outcomes:
            if odds is None:
                continue
            player = resolve_roster_player(raw, roster)
            item = build_market(
                build_runs_player_key(player, threshold),
                "runs_player",
                label,
                {"Yes": float(odds)},
                player_name=player,
                line=str(threshold),
            )
            if item:
                markets.append(item)
        return markets

    if "strikeout" in lower_base or "retraits sur des" in lower_base:
        player = ""
        player_match = re.search(
            r"(?:strikeouts?|retraits sur des(?: prises)?)\s*(?:du joueur)?\s*-?\s*(.+)$",
            lower_base,
        ) or re.search(
            r"^(.+?)\s*-\s*(?:nombre (?:total )?de )?(?:strikeouts?|retraits sur des(?: prises)?)$",
            lower_base,
        )
        if player_match:
            player = resolve_roster_player(player_match.group(1).strip(" -"), roster)
        by_line: dict[str, dict[str, float]] = {}
        for raw, odds in outcomes:
            if odds is None:
                continue
            m = re.match(r"^(.+?)\s*([+-])\s*de\s*([\d.,]+)", raw, flags=re.I)
            if m:
                player = resolve_roster_player(m.group(1), roster)
                line = format_line(m.group(3))
                side = "Over" if m.group(2) == "+" else "Under"
                by_line.setdefault(line, {})[side] = float(odds)
                continue
            line = parse_french_number(raw) or _extract_line_from_label(label)
            side = normalize_ou_label(raw)
            if line is None or side not in {"Over", "Under"} or not player:
                continue
            by_line.setdefault(format_line(line), {})[side] = float(odds)
        for line_key, outcome_map in by_line.items():
            item = build_market(
                build_strikeouts_pitcher_key(player, line_key),
                "strikeouts_pitcher",
                label,
                outcome_map,
                player_name=player,
                line=line_key,
            )
            if item:
                markets.append(item)
        return markets

    return markets


def normalized_market_to_dict(item: NormalizedMarket) -> dict:
    return {
        "compare_key": item.compare_key,
        "market_family": item.market_family,
        "market_label_raw": item.market_label_raw,
        "player_name": item.player_name,
        "line": item.line,
        "outcomes": {outcome.label: outcome.odds for outcome in item.outcomes},
    }


BOOK_NORMALIZERS = {
    "unibet": normalize_unibet_market,
    "betclic": normalize_betclic_market,
    "winamax": normalize_winamax_market,
}
