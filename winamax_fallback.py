"""Relais Winamax via l'app Vercel (egress non datacenter) quand le runner EU est bloqué."""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = float(os.environ.get("WINAMAX_FALLBACK_TIMEOUT", "45"))


def _fallback_config() -> tuple[str | None, str | None]:
    base = (
        os.environ.get("WINAMAX_FALLBACK_URL")
        or os.environ.get("WEB_APP_URL")
        or os.environ.get("VERCEL_URL")
        or ""
    ).strip().rstrip("/")
    if base and not base.startswith("http"):
        base = f"https://{base}"
    secret = (
        os.environ.get("WINAMAX_FALLBACK_SECRET")
        or os.environ.get("RUNNER_SECRET")
        or ""
    ).strip()
    return (base or None, secret or None)


def winamax_fallback_enabled() -> bool:
    base, secret = _fallback_config()
    return bool(base and secret)


def _fallback_headers(secret: str) -> dict[str, str]:
    headers = {"X-Runner-Secret": secret}
    bypass = (os.environ.get("WINAMAX_FALLBACK_BYPASS") or "").strip()
    if bypass:
        headers["x-vercel-protection-bypass"] = bypass
    return headers


def _get_fallback_json(path: str, *, params: dict[str, str]) -> dict[str, Any] | None:
    base, secret = _fallback_config()
    if not base or not secret:
        return None
    url = f"{base}{path}"
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
            "Winamax fallback HTTP %s: %s",
            response.status_code,
            (data.get("error") or data.get("message") or "")[:160],
        )
        return None
    payload = data.get("payload")
    return payload if isinstance(payload, dict) else None


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
