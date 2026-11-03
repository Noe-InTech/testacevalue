"""Relais Winamax via l'app Vercel (egress non datacenter) quand le runner EU est bloqué."""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

import requests

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = float(os.environ.get("WINAMAX_FALLBACK_TIMEOUT", "45"))
_EXTRA_URLS_FILE = (
    Path(__file__).resolve().parent / "runner" / "data" / "winamax_fallback_urls.txt"
)

# Relais prod (Vercel) — utilisé automatiquement sur RUNNER_ROLE=eu si RUNNER_SECRET est défini.
BUILTIN_EU_FALLBACK_BASES: tuple[str, ...] = (
    "https://testacevalue-eight.vercel.app",
)

_LAST_GOOD_BASE: str | None = None
_RELAY_LOCK = threading.Lock()
_RELAY_STATUS: dict[str, Any] = {
    "ok": None,
    "message": "Pas encore sonde.",
    "active_base": None,
    "bases_configured": [],
    "match_count": None,
    "checked_at": None,
    "datacenter_blocked": None,
}


def _normalize_base(url: str) -> str | None:
    text = str(url or "").strip().rstrip("/")
    if not text:
        return None
    if not text.startswith("http"):
        text = f"https://{text}"
    return text


def _fallback_secret() -> str | None:
    secret = (
        os.environ.get("WINAMAX_FALLBACK_SECRET")
        or os.environ.get("RUNNER_SECRET")
        or ""
    ).strip()
    return secret or None


def _auto_builtin_fallback_allowed() -> bool:
    role = (os.environ.get("RUNNER_ROLE") or "eu").strip().lower()
    if role != "eu":
        return False
    disabled = (os.environ.get("WINAMAX_DISABLE_BUILTIN_FALLBACK") or "").strip().lower()
    if disabled in {"1", "true", "yes", "on"}:
        return False
    return _fallback_secret() is not None


def _urls_from_extra_file() -> list[str]:
    path = Path(os.environ.get("WINAMAX_FALLBACK_URLS_FILE", str(_EXTRA_URLS_FILE)))
    if not path.is_file():
        return []
    lines: list[str] = []
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            text = raw.strip()
            if not text or text.startswith("#"):
                continue
            lines.append(text)
    except OSError as exc:
        log.warning("Lecture %s impossible: %s", path, exc)
    return lines


def fallback_base_urls() -> list[str]:
    """URLs de relais dans l'ordre de preference (deduplique)."""
    seen: set[str] = set()
    ordered: list[str] = []

    def add(raw: str | None) -> None:
        base = _normalize_base(raw or "")
        if base and base not in seen:
            seen.add(base)
            ordered.append(base)

    for part in (os.environ.get("WINAMAX_FALLBACK_URLS") or "").split(","):
        add(part)
    add(os.environ.get("WINAMAX_FALLBACK_URL"))
    for line in _urls_from_extra_file():
        add(line)
    add(os.environ.get("WEB_APP_URL"))
    add(os.environ.get("VERCEL_URL"))
    if _auto_builtin_fallback_allowed():
        for builtin in BUILTIN_EU_FALLBACK_BASES:
            add(builtin)
    return ordered


def _fallback_config() -> tuple[str | None, str | None]:
    bases = fallback_base_urls()
    secret = _fallback_secret()
    if not bases or not secret:
        return None, secret
    global _LAST_GOOD_BASE
    if _LAST_GOOD_BASE and _LAST_GOOD_BASE in bases:
        return _LAST_GOOD_BASE, secret
    return bases[0], secret


def winamax_fallback_enabled() -> bool:
    return bool(fallback_base_urls()) and _fallback_secret() is not None


def _fallback_headers(secret: str) -> dict[str, str]:
    headers = {"X-Runner-Secret": secret}
    bypass = (os.environ.get("WINAMAX_FALLBACK_BYPASS") or "").strip()
    if bypass:
        headers["x-vercel-protection-bypass"] = bypass
    return headers


def _get_fallback_json_from_base(
    base: str,
    secret: str,
    path: str,
    *,
    params: dict[str, str],
) -> dict[str, Any] | None:
    url = f"{base.rstrip('/')}{path}"
    try:
        response = requests.get(
            url,
            params=params,
            headers=_fallback_headers(secret),
            timeout=DEFAULT_TIMEOUT,
        )
    except requests.RequestException as exc:
        log.warning("Winamax fallback injoignable (%s): %s", base, exc)
        return None
    try:
        data = response.json()
    except Exception:
        data = {}
    if response.status_code >= 400 or not data.get("ok"):
        log.warning(
            "Winamax fallback HTTP %s (%s): %s",
            response.status_code,
            base,
            (data.get("error") or data.get("message") or "")[:160],
        )
        return None
    payload = data.get("payload")
    return payload if isinstance(payload, dict) else None


def _ordered_bases_for_attempt() -> list[str]:
    bases = fallback_base_urls()
    if not bases:
        return []
    global _LAST_GOOD_BASE
    if _LAST_GOOD_BASE and _LAST_GOOD_BASE in bases:
        return [_LAST_GOOD_BASE] + [b for b in bases if b != _LAST_GOOD_BASE]
    return bases


def _get_fallback_json(path: str, *, params: dict[str, str]) -> dict[str, Any] | None:
    global _LAST_GOOD_BASE
    secret = _fallback_secret()
    if not secret:
        return None
    for base in _ordered_bases_for_attempt():
        payload = _get_fallback_json_from_base(base, secret, path, params=params)
        if payload is not None:
            _LAST_GOOD_BASE = base
            return payload
    _LAST_GOOD_BASE = None
    return None


def fetch_sport_payload_via_fallback(sport_id: int) -> dict[str, Any] | None:
    return _get_fallback_json("/api/winamax-list", params={"sport": str(sport_id)})


def fetch_match_payload_via_fallback(match_id: str) -> dict[str, Any] | None:
    mid = str(match_id).strip()
    if not mid.isdigit():
        return None
    return _get_fallback_json("/api/winamax-match", params={"matchId": mid})


def fetch_route_payload_via_fallback(route: str) -> dict[str, Any] | None:
    text = str(route).strip()
    if text.startswith("match:"):
        return fetch_match_payload_via_fallback(text.split(":", 1)[1])
    if text.startswith("sport:"):
        try:
            sport_id = int(text.split(":", 1)[1])
        except (IndexError, ValueError):
            return None
        return fetch_sport_payload_via_fallback(sport_id)
    return None


def _count_basketball_matches(payload: dict[str, Any] | None) -> int:
    if not payload:
        return 0
    matches = payload.get("matches")
    if isinstance(matches, dict):
        return len(matches)
    if isinstance(matches, list):
        return len(matches)
    return 0


def get_winamax_relay_status() -> dict[str, Any]:
    with _RELAY_LOCK:
        return dict(_RELAY_STATUS)


def probe_winamax_relay(*, sport_id: int = 2) -> dict[str, Any]:
    """Sonde le relais (toutes les URLs) — appele par le watchdog runner EU."""
    global _LAST_GOOD_BASE
    from winamax_client import is_winamax_datacenter_feed_blocked

    checked_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    bases = fallback_base_urls()
    secret = _fallback_secret()
    blocked = is_winamax_datacenter_feed_blocked(refresh=True)
    status: dict[str, Any] = {
        "ok": False,
        "message": "",
        "active_base": _LAST_GOOD_BASE,
        "bases_configured": bases,
        "match_count": 0,
        "checked_at": checked_at,
        "datacenter_blocked": blocked,
        "fallback_enabled": winamax_fallback_enabled(),
    }
    if not winamax_fallback_enabled():
        status["message"] = "Relais Winamax desactive (secret ou URL manquant)."
        _store_relay_status(status)
        return status

    payload: dict[str, Any] | None = None
    for base in _ordered_bases_for_attempt():
        payload = _get_fallback_json_from_base(
            base,
            secret or "",
            "/api/winamax-list",
            params={"sport": str(sport_id)},
        )
        if payload is not None:
            _LAST_GOOD_BASE = base
            status["active_base"] = base
            break

    count = _count_basketball_matches(payload)
    status["match_count"] = count
    if payload is not None and count > 0:
        status["ok"] = True
        status["message"] = f"Relais OK ({count} match(s) basket)."
    elif payload is not None:
        status["ok"] = True
        status["message"] = "Relais repond mais 0 match basket (hors creneau ou filtre Winamax)."
    else:
        status["message"] = "Tous les relais Winamax ont echoue — retry auto au prochain scrape."
        _LAST_GOOD_BASE = None

    _store_relay_status(status)
    if not status["ok"]:
        log.warning("Winamax relay probe: %s", status["message"])
    return status


def _store_relay_status(status: dict[str, Any]) -> None:
    with _RELAY_LOCK:
        _RELAY_STATUS.clear()
        _RELAY_STATUS.update(status)


def start_winamax_relay_watchdog() -> None:
    """Thread daemon : re-sonde le relais et reinitialise l'URL sticky si besoin."""
    role = (os.environ.get("RUNNER_ROLE") or "eu").strip().lower()
    if role != "eu":
        return
    if not winamax_fallback_enabled():
        return
    try:
        interval = max(60, int(os.environ.get("WINAMAX_PROBE_SECONDS", "300")))
    except ValueError:
        interval = 300

    def loop() -> None:
        time.sleep(min(30, interval))
        while True:
            try:
                probe_winamax_relay()
            except Exception as exc:
                log.warning("Winamax relay watchdog: %s", exc)
            time.sleep(interval)

    thread = threading.Thread(target=loop, name="winamax-relay-watchdog", daemon=True)
    thread.start()
    log.info("Winamax relay watchdog actif (interval=%ss)", interval)
