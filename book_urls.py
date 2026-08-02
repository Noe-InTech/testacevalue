"""Résolution d'URL de match FR (Unibet / Betclic / Winamax) pour une ligne comparable."""

from __future__ import annotations

from typing import Any, Mapping


BOOK_LABEL_TO_KEY = {
    "unibet": "unibet",
    "betclic": "betclic",
    "winamax": "winamax",
}


def bookmaker_to_key(bookmaker: str | None) -> str:
    text = str(bookmaker or "").strip().lower()
    if not text:
        return ""
    for label, key in BOOK_LABEL_TO_KEY.items():
        if label in text:
            return key
    return ""


def resolve_fr_book_url(
    bookmaker: str | None,
    urls: Mapping[str, Any] | None = None,
    book_events: Mapping[str, Any] | None = None,
) -> str:
    """Retourne l'URL match du book FR retenu, ou chaîne vide."""
    key = bookmaker_to_key(bookmaker)
    if not key:
        return ""
    if book_events:
        event = book_events.get(key) or {}
        if isinstance(event, dict):
            url = str(event.get("url") or "").strip()
            if url:
                return url
    if urls:
        url = str(urls.get(key) or "").strip()
        if url:
            return url
    return ""


def attach_fr_book_urls(
    rows: list[dict[str, Any]],
    *,
    urls: Mapping[str, Any] | None = None,
    book_events: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    for row in rows:
        bookmaker = row.get("bookmaker_fr") or row.get("best_fr_bookmaker") or ""
        row["url_fr"] = resolve_fr_book_url(str(bookmaker), urls=urls, book_events=book_events)
    return rows
