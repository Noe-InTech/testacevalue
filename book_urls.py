"""Résolution d'URL de match / sélection FR (Unibet / Betclic / Winamax)."""

from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from tennis_books_mapping import normalize_ou_label, strip_accents


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


def build_fr_book_url(
    bookmaker: str | None,
    match_url: str,
    *,
    selection_id: str | None = None,
) -> str:
    """URL match, enrichie en deep-link sélection quand possible (Unibet)."""
    base = str(match_url or "").strip()
    if not base:
        return ""
    key = bookmaker_to_key(bookmaker)
    sid = str(selection_id or "").strip()
    if key == "unibet" and sid:
        parts = urlsplit(base)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query["outcomeIds"] = sid
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )
    return base


def selection_id_for_normalized_outcome(
    *,
    normalized_outcome: str,
    raw_outcomes: list[tuple[str, float | None]],
    selection_ids: Mapping[str, Any] | None,
    home: str = "",
    away: str = "",
) -> str:
    """Retrouve l'ID Unibet d'une issue normalisée (Over/Under/home/away/Yes…)."""
    ids = {
        str(label): str(selection_id)
        for label, selection_id in (selection_ids or {}).items()
        if selection_id
    }
    if not ids:
        return ""

    target = str(normalized_outcome or "").strip()
    if not target:
        return ""

    # 1) Match O/U
    if target in {"Over", "Under"}:
        for raw, _odds in raw_outcomes:
            if normalize_ou_label(raw) == target and raw in ids:
                return ids[raw]
            lower = strip_accents(raw)
            if target == "Over" and ("plus" in lower or lower.startswith("+")) and raw in ids:
                return ids[raw]
            if target == "Under" and ("moins" in lower or lower.startswith("-")) and raw in ids:
                return ids[raw]

    # 2) Yes / single-selection markets
    if target in {"Yes", "Oui"} and len(ids) == 1:
        return next(iter(ids.values()))

    # 3) Team / player side — exact then fuzzy token
    target_lower = strip_accents(target)
    for raw, _odds in raw_outcomes:
        if raw not in ids:
            continue
        raw_lower = strip_accents(raw)
        if raw_lower == target_lower or target_lower in raw_lower or raw_lower in target_lower:
            return ids[raw]
        if home and target in {"home", home}:
            if strip_accents(home) in raw_lower or raw_lower in strip_accents(home):
                return ids[raw]
        if away and target in {"away", away}:
            if strip_accents(away) in raw_lower or raw_lower in strip_accents(away):
                return ids[raw]

    # 4) Fallback: unique odds match
    for raw, odds in raw_outcomes:
        if raw not in ids or odds is None:
            continue
        # no normalized odds here — skip
        break
    return ""


def attach_fr_book_urls(
    rows: list[dict[str, Any]],
    *,
    urls: Mapping[str, Any] | None = None,
    book_events: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    for row in rows:
        bookmaker = row.get("bookmaker_fr") or row.get("best_fr_bookmaker") or ""
        match_url = resolve_fr_book_url(str(bookmaker), urls=urls, book_events=book_events)
        selection_id = str(row.get("selection_id") or "").strip()
        deep_url = build_fr_book_url(
            str(bookmaker),
            match_url,
            selection_id=selection_id,
        )
        row["url_fr"] = deep_url
        row["url_fr_kind"] = (
            "selection"
            if selection_id
            and bookmaker_to_key(str(bookmaker)) == "unibet"
            and "outcomeIds=" in deep_url
            else "match"
        )
    return rows
