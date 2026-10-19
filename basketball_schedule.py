"""Fenêtre horaire NBA (8 / 12 / 24 / 48 h) — filtre calendriers et ancres."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

NBA_SCHEDULE_HOUR_OPTIONS = (8, 12, 24, 48)


def normalize_nba_hours(raw: Any) -> int:
    if raw is None:
        return 12
    try:
        hours = int(raw)
    except (TypeError, ValueError):
        return 12
    return hours if hours in NBA_SCHEDULE_HOUR_OPTIONS else 12


def listing_matches_text_filter(
    home: str,
    away: str,
    needle: str,
    *,
    extra: str = "",
) -> bool:
    text = str(needle or "").strip().lower()
    if not text:
        return True
    blob = f"{home} {away} {extra}".lower()
    return text in blob


def nba_schedule_empty_hint(
    fanduel_events: list[Any],
    *,
    hours: int,
    now: datetime | None = None,
) -> str | None:
    """Message utile quand la fenêtre horaire ne retient aucun match FanDuel."""
    if not fanduel_events:
        return "FanDuel: aucun match NBA listé (hors saison ou scrape vide)."
    window = normalize_nba_hours(hours)
    now_dt = now or datetime.now(timezone.utc)
    in_window = [
        event
        for event in fanduel_events
        if _within_window(
            parse_basketball_start(getattr(event, "open_date", "")),
            now=now_dt,
            end=now_dt + timedelta(hours=window),
        )
    ]
    if in_window:
        return None
    in_48 = [
        event
        for event in fanduel_events
        if _within_window(
            parse_basketball_start(getattr(event, "open_date", "")),
            now=now_dt,
            end=now_dt + timedelta(hours=48),
        )
    ]
    dated: list[tuple[datetime, Any]] = []
    for event in fanduel_events:
        start = parse_basketball_start(getattr(event, "open_date", ""))
        if start and start >= now_dt:
            dated.append((start, event))
    dated.sort(key=lambda item: item[0])
    next_line = ""
    if dated:
        start, event = dated[0]
        delta_h = (start - now_dt).total_seconds() / 3600.0
        next_line = (
            f" Prochain: {getattr(event, 'name', '')} dans ~{delta_h:.0f}h "
            f"({start.strftime('%Y-%m-%d %H:%M')} UTC)."
        )
    if in_48:
        return (
            f"Aucun match NBA dans les {window}h.{next_line} "
            f"{len(in_48)} match(s) FanDuel dans les 48h — choisis 24h ou 48h."
        )
    return f"Aucun match NBA à venir dans les 48h.{next_line}"


def parse_basketball_start(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if isinstance(raw, (int, float)):
        ts = float(raw)
        if ts > 1e12:
            ts /= 1000.0
        if ts <= 0:
            return None
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    text = str(raw).strip()
    if not text:
        return None
    if text.isdigit():
        return parse_basketball_start(int(text))
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _within_window(
    start: datetime | None,
    *,
    now: datetime,
    end: datetime,
) -> bool:
    if start is None:
        return False
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    return now <= start <= end


def filter_nba_listings_by_hours(
    *,
    unibet_events: list[Any],
    betclic_links: list[Any],
    winamax_links: list[Any],
    fanduel_events: list[Any],
    hours: int,
    teams_match: Callable[[str, str, str, str], bool],
    now: datetime | None = None,
) -> tuple[list[Any], list[Any], list[Any], list[Any], str | None]:
    """Ne garde que les matchs dont le coup d'envoi est dans les ``hours`` prochaines heures."""
    window = normalize_nba_hours(hours)
    now_dt = now or datetime.now(timezone.utc)
    end_dt = now_dt + timedelta(hours=window)

    fd_in_window: list[Any] = []
    for event in fanduel_events:
        if _within_window(parse_basketball_start(getattr(event, "open_date", "")), now=now_dt, end=end_dt):
            fd_in_window.append(event)

    wx_in_window: list[Any] = []
    for link in winamax_links:
        if _within_window(parse_basketball_start(getattr(link, "start_date", "")), now=now_dt, end=end_dt):
            wx_in_window.append(link)

    timed_refs: list[tuple[str, str]] = [
        (item.home_team, item.away_team) for item in fd_in_window
    ] + [(item.home_team, item.away_team) for item in wx_in_window]

    def matches_timed_ref(home: str, away: str) -> bool:
        for ref_home, ref_away in timed_refs:
            if teams_match(home, away, ref_home, ref_away):
                return True
        return False

    uni_filtered = [
        event
        for event in unibet_events
        if matches_timed_ref(event.home_team, event.away_team)
    ]
    bet_filtered = [
        link
        for link in betclic_links
        if matches_timed_ref(link.home_team, link.away_team)
    ]

    note: str | None = None
    if timed_refs:
        note = (
            f"Filtre NBA {window}h — "
            f"FanDuel {len(fd_in_window)}/{len(fanduel_events)}, "
            f"Winamax {len(wx_in_window)}/{len(winamax_links)}, "
            f"Unibet {len(uni_filtered)}/{len(unibet_events)}, "
            f"Betclic {len(bet_filtered)}/{len(betclic_links)}."
        )
    elif fanduel_events or winamax_links:
        note = f"Filtre NBA {window}h — aucun match avec heure de début dans la fenêtre."

    return uni_filtered, bet_filtered, wx_in_window, fd_in_window, note


def filter_nba_anchors_by_hours(
    anchors: list[dict[str, Any]],
    *,
    fanduel_events: list[Any],
    winamax_links: list[Any],
    hours: int,
    teams_match: Callable[[str, str, str, str], bool],
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    window = normalize_nba_hours(hours)
    now_dt = now or datetime.now(timezone.utc)
    end_dt = now_dt + timedelta(hours=window)

    fd_by_id = {str(item.event_id): item for item in fanduel_events}
    wx_by_id = {str(item.match_id): item for item in winamax_links}

    kept: list[dict[str, Any]] = []
    for anchor in anchors:
        start: datetime | None = None
        fd_id = anchor.get("fanduel_event_id")
        if fd_id and str(fd_id) in fd_by_id:
            start = parse_basketball_start(fd_by_id[str(fd_id)].open_date)
        if start is None:
            wx_id = anchor.get("winamax_match_id")
            if wx_id and str(wx_id) in wx_by_id:
                start = parse_basketball_start(wx_by_id[str(wx_id)].start_date)
        if _within_window(start, now=now_dt, end=end_dt):
            kept.append(anchor)
            continue
        home = str(anchor.get("home_team") or "")
        away = str(anchor.get("away_team") or "")
        matched = False
        for event in fanduel_events:
            if _within_window(parse_basketball_start(event.open_date), now=now_dt, end=end_dt) and teams_match(
                home, away, event.home_team, event.away_team
            ):
                matched = True
                break
        if not matched:
            for link in winamax_links:
                if _within_window(parse_basketball_start(link.start_date), now=now_dt, end=end_dt) and teams_match(
                    home, away, link.home_team, link.away_team
                ):
                    matched = True
                    break
        if matched:
            kept.append(anchor)
    return kept
