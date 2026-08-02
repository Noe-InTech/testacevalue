"""Client EU → runner Oracle US (Bet365). Soft-fail si US down / non configure."""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

from us_odds_merge import merge_best_us_odds_maps, tag_us_market_map

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = float(os.environ.get("US_RUNNER_TIMEOUT", "45"))


def us_runner_config() -> tuple[str | None, str | None]:
    base = (os.environ.get("US_RUNNER_URL") or "").strip().rstrip("/")
    secret = (os.environ.get("US_RUNNER_SECRET") or os.environ.get("RUNNER_SECRET") or "").strip()
    return (base or None, secret or None)


def us_runner_enabled() -> bool:
    base, secret = us_runner_config()
    return bool(base and secret)


def fetch_bet365_us_map(
    *,
    sport: str,
    home: str,
    away: str,
    families: list[str] | None = None,
) -> dict[str, Any]:
    """
    Appelle le runner US. Retourne toujours une structure exploitable:

      { ok, soft_fail, message, map, ... }

    Si US_RUNNER_URL absent ou erreur reseau → soft_fail + map {}.
    """
    base, secret = us_runner_config()
    if not base or not secret:
        return {
            "ok": False,
            "soft_fail": True,
            "message": "US_RUNNER_URL / secret non configures — Bet365 US ignore",
            "map": {},
            "source": "bet365",
        }

    url = f"{base}/api/us/bet365"
    payload = {
        "sport": sport,
        "home": home,
        "away": away,
        "families": families or [],
    }
    try:
        response = requests.post(
            url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-Runner-Secret": secret,
            },
            timeout=DEFAULT_TIMEOUT,
        )
    except requests.RequestException as exc:
        log.warning("Runner US injoignable: %s", exc)
        return {
            "ok": False,
            "soft_fail": True,
            "message": f"Runner US injoignable: {exc}",
            "map": {},
            "source": "bet365",
        }

    try:
        data = response.json()
    except Exception:
        data = {}

    if response.status_code >= 400:
        return {
            "ok": False,
            "soft_fail": True,
            "message": str(
                data.get("error") or data.get("message") or f"HTTP {response.status_code}"
            ),
            "map": {},
            "source": "bet365",
            "status_code": response.status_code,
        }

    markets = data.get("map")
    if not isinstance(markets, dict):
        markets = {}
    return {
        "ok": bool(data.get("ok", True)),
        "soft_fail": bool(data.get("soft_fail", False)),
        "message": str(data.get("message") or ""),
        "map": markets,
        "captured_at": data.get("captured_at") or "",
        "source": "bet365",
        "probe": data.get("probe"),
    }


def merge_us_map_with_bet365(
    base_us_map: dict[str, dict[str, Any]],
    *,
    sport: str,
    home: str,
    away: str,
    families: list[str] | None = None,
    base_source: str = "fanduel",
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """
    Tag la map de base, fetch Bet365 (soft-fail), merge meilleure cote.

    Retourne (merged_map, bet365_meta).
    """
    if base_us_map and any(
        (m.get("source") or "") not in {"", base_source} for m in base_us_map.values()
    ):
        tagged: dict[str, dict[str, Any]] = dict(base_us_map)
        for market in tagged.values():
            for _outcome, bundle in (market.get("outcomes") or {}).items():
                if "us_source" not in bundle:
                    bundle["us_source"] = market.get("source") or base_source
                    bundle["us_source_label"] = market.get("source_label") or ""
                    bundle["us_bookmaker"] = market.get("source_bookmaker") or ""
    else:
        tagged = tag_us_market_map(base_us_map, source=base_source) if base_us_map else {}

    meta = fetch_bet365_us_map(
        sport=sport,
        home=home,
        away=away,
        families=families,
    )
    merged = merge_best_us_odds_maps(tagged, meta.get("map") or {})
    return merged, meta
