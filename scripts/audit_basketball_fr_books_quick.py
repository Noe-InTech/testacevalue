"""Audit rapide — catégories Betclic manquantes + labels Unibet non mappés."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from basketball_books_mapping import (  # noqa: E402
    is_wnba_player_prop_label,
    normalize_betclic_market,
    normalize_unibet_market,
)
from basketball_constants import BETCLIC_BASKETBALL_GRPC_CATEGORIES  # noqa: E402
from betclic_basketball_client import BetclicBasketballClient  # noqa: E402
from betclic_client import BetclicClient  # noqa: E402
from unibet_basketball_client import UnibetBasketballClient  # noqa: E402


def betclic_audit(link) -> dict:
    client = BetclicBasketballClient()
    raw = BetclicClient()
    base = raw.get_match_payload(link.url)
    cats = [str(c.get("id")) for c in (base.get("match") or {}).get("categories") or [] if c.get("id")]
    missing = [c for c in cats if c.startswith("ca_bkb") and c not in BETCLIC_BASKETBALL_GRPC_CATEGORIES]
    extra = [c for c in BETCLIC_BASKETBALL_GRPC_CATEGORIES if c not in cats]
    payload = client.build_event_payload(link)
    roster = payload.get("roster") or []
    unmapped = []
    norm_count = 0
    prop_labels = []
    for m in payload.get("markets", []):
        label = str(m.get("label", "")).strip()
        if not is_wnba_player_prop_label(label):
            continue
        prop_labels.append(label)
        outs = [(str(a), b) for a, b in m.get("outcomes", [])]
        norm = normalize_betclic_market(label, outs, roster)
        if norm:
            norm_count += len(norm)
        else:
            unmapped.append(label)
    ssr_only = raw.extract_markets_from_match_payload(base)
    ssr_props = [m.label for m in ssr_only if is_wnba_player_prop_label(m.label)]
    return {
        "match": f"{link.home_team} vs {link.away_team}",
        "url": link.url,
        "all_bkb_categories": [c for c in cats if c.startswith("ca_bkb")],
        "configured_grpc": list(BETCLIC_BASKETBALL_GRPC_CATEGORIES),
        "missing_from_config": missing,
        "config_not_on_match": extra,
        "market_count": payload.get("market_count"),
        "ssr_prop_labels": ssr_props,
        "merged_prop_labels": prop_labels,
        "normalized_slots": norm_count,
        "unmapped": unmapped,
    }


def unibet_audit(event) -> dict:
    client = UnibetBasketballClient()
    payload = client.build_event_payload(event)
    roster = payload.get("roster") or []
    unmapped = []
    skipped_playerish = []
    norm_count = 0
    labels = []
    for m in payload.get("markets", []):
        label = str(m.get("label", "")).strip()
        low = label.lower()
        if any(x in low for x in ("joueur", "performance", "rebond", "passe", "3 pt", "double", "paniers")):
            if not is_wnba_player_prop_label(label):
                skipped_playerish.append(label)
                continue
            labels.append(label)
            outs = [(str(a), b) for a, b in m.get("outcomes", [])]
            norm = normalize_unibet_market(label, outs, roster)
            if norm:
                norm_count += len(norm)
            else:
                unmapped.append(label)
    return {
        "match": event.name,
        "url": event.url,
        "market_count": payload.get("market_count"),
        "prop_labels": labels,
        "normalized_slots": norm_count,
        "unmapped": unmapped,
        "skipped_playerish": skipped_playerish,
    }


def main() -> None:
    bc = BetclicBasketballClient()
    ub = UnibetBasketballClient()
    nba = bc.list_nba_matches()
    events = ub.list_nba_events()
    link = next(
        (m for m in nba if "pistons" in m.slug and "celtics" in m.slug),
        nba[0] if nba else None,
    )
    ev = next(
        (e for e in events if "pistons" in e.name.lower()),
        events[0] if events else None,
    )
    out = {}
    if link:
        out["betclic"] = betclic_audit(link)
    if ev:
        out["unibet"] = unibet_audit(ev)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
