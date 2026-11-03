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


def fetch_sport_payload_via_fallback(sport_id: int) -> dict[str, Any] | None:
    base, secret = _fallback_config()
    if not base or not secret:
        return None
    url = f"{base}/api/winamax-list"
    headers = {"X-Runner-Secret": secret}
    bypass = (os.environ.get("WINAMAX_FALLBACK_BYPASS") or "").strip()
    if bypass:
        headers["x-vercel-protection-bypass"] = bypass

    try:
        response = requests.get(
            url,
            params={"sport": str(sport_id)},
            headers=headers,
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
