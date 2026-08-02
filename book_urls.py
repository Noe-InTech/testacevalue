"""Résolution d'URL de match / sélection FR (Unibet / Betclic / Winamax)."""

from __future__ import annotations

import re
from typing import Any, Callable, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from tennis_books_mapping import normalize_ou_label, strip_accents


BOOK_LABEL_TO_KEY = {
    "unibet": "unibet",
    "betclic": "betclic",
    "winamax": "winamax",
}

BetclicShareResolver = Callable[[str, str, str], str]


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


def split_compound_selection_id(selection_id: str | None) -> tuple[str, str]:
    """Decode `left:right` (Winamax betId:oddId, Betclic selection:market)."""
    text = str(selection_id or "").strip()
    if not text or ":" not in text:
        return "", ""
    left, right = text.split(":", 1)
    return left.strip(), right.strip()


def match_id_from_book_url(bookmaker: str | None, match_url: str) -> str:
    key = bookmaker_to_key(bookmaker)
    url = str(match_url or "").strip()
    if not url:
        return ""
    if key == "betclic":
        match = re.search(r"-m(\d+)/?(?:[?#]|$)", url)
        return match.group(1) if match else ""
    if key == "winamax":
        match = re.search(r"/match/(\d+)", url)
        return match.group(1) if match else ""
    return ""


def build_winamax_wam_url(*, match_id: str, bet_id: str, odd_id: str) -> str:
    """Deeplink officiel qui ajoute la sélection au panier (app / navigateBetting)."""
    mid = str(match_id or "").strip()
    bid = str(bet_id or "").strip()
    oid = str(odd_id or "").strip()
    if not mid or not bid or not oid:
        return ""
    return f"wam://betting?target=match-{mid}&b={bid}&o={oid}"


def build_winamax_web_fallback_url(match_url: str, *, bet_id: str, odd_id: str) -> str:
    """Page match HTTPS avec hash #b/#o (highlight marché — pas d'ajout panier seul)."""
    base = str(match_url or "").strip()
    bid = str(bet_id or "").strip()
    oid = str(odd_id or "").strip()
    if not base or not bid or not oid:
        return base
    parts = urlsplit(base)
    fragment = f"b={bid}&o={oid}"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, fragment))


def build_fr_book_url(
    bookmaker: str | None,
    match_url: str,
    *,
    selection_id: str | None = None,
    match_id: str | None = None,
    resolve_betclic_share: BetclicShareResolver | None = None,
) -> str:
    """URL match, enrichie en deep-link sélection quand possible."""
    base = str(match_url or "").strip()
    if not base:
        return ""
    key = bookmaker_to_key(bookmaker)
    sid = str(selection_id or "").strip()
    if not sid:
        return base

    if key == "unibet":
        parts = urlsplit(base)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query["outcomeIds"] = sid
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )

    if key == "winamax":
        bet_id, odd_id = split_compound_selection_id(sid)
        event_id = str(match_id or "").strip() or match_id_from_book_url(key, base)
        if not event_id or not bet_id or not odd_id:
            return base
        # Bridge page: tries wam:// (adds to betslip) then HTTPS match fallback.
        return f"/go/winamax?{urlencode({'match': event_id, 'b': bet_id, 'o': odd_id})}"

    if key == "betclic":
        sel_id, market_id = split_compound_selection_id(sid)
        event_id = str(match_id or "").strip() or match_id_from_book_url(key, base)
        if not sel_id or not market_id or not event_id or resolve_betclic_share is None:
            return base
        try:
            share_url = str(
                resolve_betclic_share(sel_id, event_id, market_id) or ""
            ).strip()
        except Exception:
            return base
        return share_url or base

    return base


def selection_id_for_normalized_outcome(
    *,
    normalized_outcome: str,
    raw_outcomes: list[tuple[str, float | None]],
    selection_ids: Mapping[str, Any] | None,
    home: str = "",
    away: str = "",
) -> str:
    """Retrouve l'ID sélection d'une issue normalisée (Over/Under/home/away/Yes…)."""
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


def _default_betclic_share_resolver() -> BetclicShareResolver | None:
    try:
        from betclic_client import BetclicClient
    except Exception:
        return None
    client = BetclicClient()
    cache: dict[tuple[str, str, str], str] = {}

    def resolve(selection_id: str, match_id: str, market_id: str) -> str:
        key = (selection_id, match_id, market_id)
        cached = cache.get(key)
        if cached is not None:
            return cached
        url = client.create_share_url(
            selection_id=selection_id,
            match_id=match_id,
            market_id=market_id,
        )
        cache[key] = url
        return url

    return resolve


def _selection_url_kind(bookmaker: str | None, deep_url: str, selection_id: str) -> str:
    key = bookmaker_to_key(bookmaker)
    if not selection_id or not deep_url:
        return "match"
    if key == "unibet" and "outcomeIds=" in deep_url:
        return "selection"
    if key == "winamax" and deep_url.startswith("/go/winamax?"):
        return "selection"
    if key == "winamax" and deep_url.startswith("wam://betting?") and "b=" in deep_url and "o=" in deep_url:
        return "selection"
    if key == "betclic" and "/bet/" in deep_url:
        return "selection"
    return "match"


def attach_fr_book_urls(
    rows: list[dict[str, Any]],
    *,
    urls: Mapping[str, Any] | None = None,
    book_events: Mapping[str, Any] | None = None,
    resolve_betclic_share: BetclicShareResolver | None | bool = True,
) -> list[dict[str, Any]]:
    share_resolver: BetclicShareResolver | None
    if resolve_betclic_share is True:
        share_resolver = _default_betclic_share_resolver()
    elif resolve_betclic_share is False or resolve_betclic_share is None:
        share_resolver = None
    else:
        share_resolver = resolve_betclic_share

    for row in rows:
        bookmaker = row.get("bookmaker_fr") or row.get("best_fr_bookmaker") or ""
        key = bookmaker_to_key(str(bookmaker))
        match_url = resolve_fr_book_url(str(bookmaker), urls=urls, book_events=book_events)
        selection_id = str(row.get("selection_id") or "").strip()
        match_id = ""
        if book_events and key:
            event = book_events.get(key) or {}
            if isinstance(event, dict):
                match_id = str(event.get("match_id") or "").strip()
        if not match_id:
            match_id = match_id_from_book_url(str(bookmaker), match_url)
        deep_url = build_fr_book_url(
            str(bookmaker),
            match_url,
            selection_id=selection_id,
            match_id=match_id,
            resolve_betclic_share=share_resolver if key == "betclic" else None,
        )
        row["url_fr"] = deep_url
        row["url_fr_kind"] = _selection_url_kind(str(bookmaker), deep_url, selection_id)
        row.pop("url_fr_web", None)
        if key == "winamax" and selection_id and row["url_fr_kind"] == "selection":
            bet_id, odd_id = split_compound_selection_id(selection_id)
            web = build_winamax_web_fallback_url(
                match_url, bet_id=bet_id, odd_id=odd_id
            )
            if web:
                row["url_fr_web"] = web
    return rows
