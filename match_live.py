"""Helpers pour marquer les matchs en cours (live) sur les anchors / lignes."""

from __future__ import annotations

from typing import Any, Iterable


def unibet_url_is_live(url: str | None) -> bool:
    return "/paris-en-direct/" in str(url or "")


def winamax_status_is_live(status: str | None) -> bool:
    return str(status or "").strip().upper() == "LIVE"


def event_is_live(
    *,
    is_live: Any = None,
    url: str | None = None,
    status: str | None = None,
) -> bool:
    if is_live is True or str(is_live).strip().lower() in {"1", "true", "yes"}:
        return True
    if unibet_url_is_live(url):
        return True
    if winamax_status_is_live(status):
        return True
    return False


def mark_anchor_live(anchor: dict[str, Any], live: bool) -> None:
    if live:
        anchor["is_live"] = True
    else:
        anchor.setdefault("is_live", False)


def stamp_rows_live(rows: Iterable[dict[str, Any]], is_live: bool) -> None:
    flag = bool(is_live)
    for row in rows:
        row["is_live"] = flag
