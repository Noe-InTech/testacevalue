"""Cotes match basketball (ML / spread / total) — vérification scrape tous books."""

from __future__ import annotations

import re
from typing import Any

from fanduel_client import format_french_decimal, runner_fanduel_price_bundle
from tennis_books_mapping import strip_accents
from tennis_market_mapping import players_match

BOOK_ORDER = ("fanduel", "winamax", "unibet", "betclic")
BOOK_LABELS = {
    "fanduel": "FanDuel",
    "winamax": "Winamax",
    "unibet": "Unibet",
    "betclic": "Betclic",
}


def _fmt_odds(value: float | None) -> str | None:
    if value is None:
        return None
    try:
        return format_french_decimal(float(value))
    except (TypeError, ValueError):
        return None


def _team_side(name: str, *, home: str, away: str) -> str | None:
    text = str(name or "").strip()
    if not text:
        return None
    if players_match(text, home):
        return "home"
    if players_match(text, away):
        return "away"
    return None


def _parse_line_from_label(label: str) -> float | None:
    match = re.search(r"\(([\d.,]+)\)", str(label or ""))
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def _parse_handicap_outcome(label: str) -> tuple[str, float] | None:
    text = str(label or "").strip()
    match = re.search(r"([+-]?\d+[.,]?\d*)\s*$", text)
    if not match:
        return None
    try:
        line = float(match.group(1).replace(",", "."))
    except ValueError:
        return None
    team = text[: match.start()].strip()
    return team, line


def _is_match_moneyline_market(label: str) -> bool:
    lower = strip_accents(str(label or "").lower()).strip()
    if not lower or "joueur" in lower or "player" in lower:
        return False
    if lower in {"vainqueur", "moneyline", "match betting"}:
        return True
    if lower.startswith("vainqueur du match"):
        return True
    if "face a face" in lower and "match" in lower:
        return True
    if lower == "vainqueur (match)":
        return True
    return False


def _is_match_spread_market(label: str) -> bool:
    lower = strip_accents(str(label or "").lower())
    if "joueur" in lower or "player" in lower:
        return False
    if "handicap" in lower or lower == "spread":
        return True
    if "ecart de points" in lower:
        return True
    return False


def _is_match_total_market(label: str) -> bool:
    lower = strip_accents(str(label or "").lower())
    if "joueur" in lower or "player" in lower:
        return False
    if lower.startswith("nombre de points"):
        return True
    if lower.startswith("total points") or lower == "total points":
        return True
    if "total du match" in lower and "joueur" not in lower:
        return True
    return False


def _extract_fr_moneyline(
    markets: list[dict[str, Any]],
    *,
    home: str,
    away: str,
) -> dict[str, float | None]:
    out: dict[str, float | None] = {"home": None, "away": None}
    for market in markets:
        label = str(market.get("label") or "")
        if not _is_match_moneyline_market(label):
            continue
        if strip_accents(label.lower()).startswith("resultat"):
            continue
        for raw_outcome, odds in market.get("outcomes") or []:
            side = _team_side(str(raw_outcome), home=home, away=away)
            if side is None:
                continue
            try:
                value = float(odds)
            except (TypeError, ValueError):
                continue
            out[side] = value
        if out["home"] is not None and out["away"] is not None:
            break
    return out


def _extract_fr_spread_candidates(
    markets: list[dict[str, Any]],
    *,
    home: str,
    away: str,
) -> list[tuple[float, float | None, float | None]]:
    candidates: list[tuple[float, float | None, float | None]] = []
    for market in markets:
        label = str(market.get("label") or "")
        if not _is_match_spread_market(label):
            continue
        home_odds: float | None = None
        away_odds: float | None = None
        home_line: float | None = None
        for raw_outcome, odds in market.get("outcomes") or []:
            parsed = _parse_handicap_outcome(str(raw_outcome))
            if not parsed:
                continue
            team, line = parsed
            side = _team_side(team, home=home, away=away)
            if side is None:
                continue
            try:
                price = float(odds)
            except (TypeError, ValueError):
                continue
            if side == "home":
                home_odds = price
                home_line = line
            else:
                away_odds = price
        if home_line is not None and (home_odds is not None or away_odds is not None):
            candidates.append((home_line, home_odds, away_odds))
    return candidates


def _extract_fr_total_candidates(
    markets: list[dict[str, Any]],
) -> list[tuple[float, float | None, float | None]]:
    candidates: list[tuple[float, float | None, float | None]] = []
    for market in markets:
        label = str(market.get("label") or "")
        if not _is_match_total_market(label):
            continue
        line = _parse_line_from_label(label)
        if line is None:
            continue
        over: float | None = None
        under: float | None = None
        for raw_outcome, odds in market.get("outcomes") or []:
            lower = strip_accents(str(raw_outcome).lower())
            try:
                price = float(odds)
            except (TypeError, ValueError):
                continue
            if "plus" in lower or lower == "over":
                over = price
            elif "moins" in lower or lower == "under":
                under = price
        if over is not None or under is not None:
            candidates.append((line, over, under))
    return candidates


def _pick_closest_line(
    candidates: list[tuple[float, float | None, float | None]],
    target: float | None,
) -> tuple[float, float | None, float | None] | None:
    if not candidates:
        return None
    if target is None:
        return candidates[0]
    return min(candidates, key=lambda item: abs(item[0] - target))


def _extract_fanduel_lines(
    event: dict[str, Any] | None,
    *,
    home: str,
    away: str,
) -> dict[str, Any]:
    empty: dict[str, Any] = {
        "moneyline": {"home": None, "away": None},
        "spread": {"line": None, "home": None, "away": None},
        "total": {"line": None, "over": None, "under": None},
    }
    if not event:
        return empty
    for market in event.get("markets") or []:
        name = str(market.get("marketName") or "")
        if name == "Moneyline":
            for runner in market.get("runners") or []:
                if runner.get("runnerStatus") not in (None, "ACTIVE"):
                    continue
                bundle = runner_fanduel_price_bundle(runner)
                dec = bundle.get("decimal_fr")
                side = _team_side(str(runner.get("runnerName") or ""), home=home, away=away)
                if side and dec is not None:
                    empty["moneyline"][side] = float(dec)
        elif name == "Spread":
            for runner in market.get("runners") or []:
                if runner.get("runnerStatus") not in (None, "ACTIVE"):
                    continue
                bundle = runner_fanduel_price_bundle(runner)
                dec = bundle.get("decimal_fr")
                side = _team_side(str(runner.get("runnerName") or ""), home=home, away=away)
                handicap = runner.get("handicap")
                try:
                    line = float(handicap) if handicap is not None else None
                except (TypeError, ValueError):
                    line = None
                if side == "home" and line is not None:
                    empty["spread"]["line"] = line
                if side and dec is not None:
                    empty["spread"][side] = float(dec)
        elif name == "Total Points":
            for runner in market.get("runners") or []:
                if runner.get("runnerStatus") not in (None, "ACTIVE"):
                    continue
                bundle = runner_fanduel_price_bundle(runner)
                dec = bundle.get("decimal_fr")
                handicap = runner.get("handicap")
                try:
                    line = float(handicap) if handicap is not None else None
                except (TypeError, ValueError):
                    line = None
                if line is not None:
                    empty["total"]["line"] = line
                runner_name = str(runner.get("runnerName") or "").lower()
                if dec is None:
                    continue
                if runner_name == "over":
                    empty["total"]["over"] = float(dec)
                elif runner_name == "under":
                    empty["total"]["under"] = float(dec)
    return empty


def _book_row_from_fr(
    book_key: str,
    event: dict[str, Any] | None,
    *,
    home: str,
    away: str,
    fd_lines: dict[str, Any],
) -> dict[str, Any]:
    row: dict[str, Any] = {"book": book_key, "book_label": BOOK_LABELS.get(book_key, book_key)}
    if not event:
        return row
    markets = event.get("markets") or []
    ml = _extract_fr_moneyline(markets, home=home, away=away)
    row["moneyline_home"] = _fmt_odds(ml.get("home"))
    row["moneyline_away"] = _fmt_odds(ml.get("away"))

    spread_target = fd_lines.get("spread", {}).get("line")
    spread_pick = _pick_closest_line(
        _extract_fr_spread_candidates(markets, home=home, away=away),
        float(spread_target) if spread_target is not None else None,
    )
    if spread_pick:
        line, home_odds, away_odds = spread_pick
        row["spread_line"] = str(line).replace(".", ",") if line is not None else None
        row["spread_home"] = _fmt_odds(home_odds)
        row["spread_away"] = _fmt_odds(away_odds)

    total_target = fd_lines.get("total", {}).get("line")
    total_pick = _pick_closest_line(
        _extract_fr_total_candidates(markets),
        float(total_target) if total_target is not None else None,
    )
    if total_pick:
        line, over, under = total_pick
        row["total_line"] = str(line).replace(".", ",") if line is not None else None
        row["total_over"] = _fmt_odds(over)
        row["total_under"] = _fmt_odds(under)
    return row


def _book_row_from_fanduel(fd_lines: dict[str, Any]) -> dict[str, Any]:
    ml = fd_lines.get("moneyline") or {}
    sp = fd_lines.get("spread") or {}
    tot = fd_lines.get("total") or {}
    line_sp = sp.get("line")
    line_tot = tot.get("line")
    return {
        "book": "fanduel",
        "book_label": "FanDuel",
        "moneyline_home": _fmt_odds(ml.get("home")),
        "moneyline_away": _fmt_odds(ml.get("away")),
        "spread_line": str(line_sp).replace(".", ",") if line_sp is not None else None,
        "spread_home": _fmt_odds(sp.get("home")),
        "spread_away": _fmt_odds(sp.get("away")),
        "total_line": str(line_tot).replace(".", ",") if line_tot is not None else None,
        "total_over": _fmt_odds(tot.get("over")),
        "total_under": _fmt_odds(tot.get("under")),
    }


def build_basketball_match_odds_snapshot(
    *,
    match: str,
    home: str,
    away: str,
    book_events: dict[str, dict[str, Any]],
    fanduel_event: dict[str, Any] | None,
) -> dict[str, Any]:
    fd_lines = _extract_fanduel_lines(fanduel_event, home=home, away=away)
    rows: list[dict[str, Any]] = []
    if fanduel_event:
        rows.append(_book_row_from_fanduel(fd_lines))
    for book_key in BOOK_ORDER:
        if book_key == "fanduel":
            continue
        event = book_events.get(book_key)
        if not event:
            continue
        row = _book_row_from_fr(book_key, event, home=home, away=away, fd_lines=fd_lines)
        if any(row.get(key) for key in row if key not in {"book", "book_label"}):
            rows.append(row)
    return {
        "match": match,
        "home": home,
        "away": away,
        "books": rows,
    }


def collect_match_odds_from_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    for result in results:
        snap = result.get("match_odds")
        if isinstance(snap, dict) and snap.get("books"):
            snapshots.append(snap)
    return snapshots
