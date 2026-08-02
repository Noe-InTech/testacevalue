"""Client Bet365 US (va.bet365.com) — a executer depuis un egress US uniquement."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from bet365_us_mapping import build_normalized_map_from_bet365_markets
from us_odds_merge import tag_us_market_map

log = logging.getLogger(__name__)

BET365_US_BASE = os.environ.get("BET365_US_BASE", "https://va.bet365.com").rstrip("/")
DEFAULT_TIMEOUT = float(os.environ.get("BET365_US_TIMEOUT", "25"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    proxy = os.environ.get("BET365_PROXY", "").strip()
    if proxy:
        session.proxies.update({"http": proxy, "https": proxy})
    return session


def load_fixture_markets(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        markets = payload.get("markets")
        if isinstance(markets, list):
            return markets
    raise ValueError(f"Fixture Bet365 invalide: {path}")


def probe_bet365_us_reachable(session: requests.Session | None = None) -> dict[str, Any]:
    """Verifie que l'egress voit bien la surface US (pas une redirection .fr)."""
    sess = session or _session()
    try:
        response = sess.get(f"{BET365_US_BASE}/", timeout=DEFAULT_TIMEOUT, allow_redirects=True)
    except requests.RequestException as exc:
        return {
            "ok": False,
            "soft_fail": True,
            "message": f"Bet365 US injoignable: {exc}",
            "final_url": "",
        }
    final = str(response.url or "")
    text_l = (response.text or "")[:2000].lower()
    geo_blocked = (
        ".fr" in final
        or "bet365.fr" in final
        or "just a moment" in text_l
        or response.status_code in {403, 503}
    )
    if geo_blocked:
        return {
            "ok": False,
            "soft_fail": True,
            "message": (
                "Egress non-US detecte (redirection FR / Cloudflare). "
                "Scrape Bet365 uniquement depuis le runner US."
            ),
            "final_url": final,
            "status_code": response.status_code,
        }
    return {
        "ok": True,
        "soft_fail": False,
        "message": "Bet365 US joignable",
        "final_url": final,
        "status_code": response.status_code,
    }


def fetch_bet365_us_normalized_map(
    *,
    sport: str,
    home: str,
    away: str,
    families: set[str] | None = None,
    fixture_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    Retourne { ok, soft_fail, message, map, captured_at }.

    Modes:
    - BET365_FIXTURE_JSON / fixture_path : tests / dry-run
    - live : probe geo puis scrape (MVP : soft-fail si pas de marche parse)
    """
    captured_at = utc_now()
    path = fixture_path or os.environ.get("BET365_FIXTURE_JSON", "").strip() or None

    if path:
        try:
            markets = load_fixture_markets(path)
            variant_map = build_normalized_map_from_bet365_markets(
                markets,
                sport=sport,
                home=home,
                away=away,
                families=families,
                captured_at=captured_at,
            )
            tagged = tag_us_market_map(
                variant_map,
                source="bet365",
                captured_at=captured_at,
            )
            return {
                "ok": True,
                "soft_fail": False,
                "message": f"Fixture Bet365 ({len(tagged)} marches)",
                "map": tagged,
                "captured_at": captured_at,
                "source": "bet365",
            }
        except Exception as exc:
            return {
                "ok": False,
                "soft_fail": True,
                "message": f"Fixture Bet365 illisible: {exc}",
                "map": {},
                "captured_at": captured_at,
                "source": "bet365",
            }

    session = _session()
    probe = probe_bet365_us_reachable(session)
    if not probe.get("ok"):
        return {
            "ok": False,
            "soft_fail": True,
            "message": str(probe.get("message") or "Bet365 US soft-fail"),
            "map": {},
            "captured_at": captured_at,
            "source": "bet365",
            "probe": probe,
        }

    # Live scrape: Bet365 n'expose pas d'API publique stable.
    # Le runner US doit peupler BET365_FIXTURE_JSON ou une future couche Playwright.
    # Ici on soft-fail proprement si aucun parseur live n'est configure.
    live_enabled = os.environ.get("BET365_LIVE_SCRAPE", "").strip() in {"1", "true", "yes"}
    if not live_enabled:
        return {
            "ok": True,
            "soft_fail": True,
            "message": (
                "Bet365 US joignable mais scrape live desactive "
                "(BET365_LIVE_SCRAPE=1 + parseur a activer sur le runner US)."
            ),
            "map": {},
            "captured_at": captured_at,
            "source": "bet365",
            "probe": probe,
        }

    # Point d'extension scrape live (Playwright / blobs). Soft-fail tant que non branche.
    log.warning("BET365_LIVE_SCRAPE actif mais parseur live non implemente — map vide")
    return {
        "ok": True,
        "soft_fail": True,
        "message": "Parseur Bet365 live non implemente; map vide",
        "map": {},
        "captured_at": captured_at,
        "source": "bet365",
        "probe": probe,
    }
