"""Audit live Betclic + Unibet NBA/WNBA — catégories gRPC, labels, normalisation.

Usage: python scripts/audit_basketball_fr_books.py [--nba] [--wnba]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from basketball_books_mapping import (  # noqa: E402
    BOOK_NORMALIZERS,
    is_wnba_player_prop_label,
    normalize_betclic_market,
    normalize_unibet_market,
)
from betclic_basketball_client import BetclicBasketballClient  # noqa: E402
from betclic_client import BetclicClient  # noqa: E402
from unibet_basketball_client import UnibetBasketballClient  # noqa: E402


def _norm_keys(payload: dict, book: str, roster: list[str]) -> set[str]:
    normalizer = BOOK_NORMALIZERS[book]
    keys: set[str] = set()
    for market in payload.get("markets", []):
        label = str(market.get("label", "")).strip()
        if not is_wnba_player_prop_label(label):
            continue
        outs = [(str(a), b) for a, b in market.get("outcomes", [])]
        for item in normalizer(label, outs, roster):
            keys.add(item.compare_key)
    return keys


def audit_betclic_match(
    client: BetclicBasketballClient,
    link,
) -> dict:
    url = link.url
    base = client.get_match_payload(url)
    match = base.get("match") or {}
    category_ids = [
        str(c.get("id", "")) for c in (match.get("categories") or []) if c.get("id")
    ]
    per_cat: dict[str, int] = {}
    prop_labels_by_cat: dict[str, list[str]] = {}
    raw_client = BetclicClient()
    for cat in category_ids:
        grpc = raw_client.fetch_grpc_match_payload(url, category_id=cat)
        if not grpc:
            per_cat[cat] = 0
            continue
        markets = raw_client.extract_markets_from_match_payload(grpc)
        per_cat[cat] = len(markets)
        props = [
            m.label
            for m in markets
            if is_wnba_player_prop_label(m.label)
            or any(
                tok in m.label.lower()
                for tok in ("joueur", "performance", "rebond", "passe", "3 point", "double")
            )
        ]
        if props:
            prop_labels_by_cat[cat] = sorted(set(props))

    full = client.build_event_payload(link)
    roster = full.get("roster") or []
    keys = _norm_keys(full, "betclic", roster)
    unmapped: list[str] = []
    for market in full.get("markets", []):
        label = str(market.get("label", "")).strip()
        if not is_wnba_player_prop_label(label):
            continue
        outs = [(str(a), b) for a, b in market.get("outcomes", [])]
        if not normalize_betclic_market(label, outs, roster):
            unmapped.append(label)

    return {
        "url": url,
        "categories": category_ids,
        "markets_per_grpc_category": per_cat,
        "prop_labels_by_category": prop_labels_by_cat,
        "market_count": full.get("market_count"),
        "grpc_hits": full.get("markets") and "via build",
        "normalized_keys": len(keys),
        "unmapped_prop_labels": unmapped,
    }


def audit_unibet_event(client: UnibetBasketballClient, event) -> dict:
    payload = client.build_event_payload(event)
    roster = payload.get("roster") or []
    keys = _norm_keys(payload, "unibet", roster)
    unmapped: list[str] = []
    playerish_unmapped: list[str] = []
    for market in payload.get("markets", []):
        label = str(market.get("label", "")).strip()
        lower = label.lower()
        if any(tok in lower for tok in ("joueur", "performance", "rebond", "passe", "3 pt", "double")):
            if not is_wnba_player_prop_label(label):
                playerish_unmapped.append(label)
                continue
            outs = [(str(a), b) for a, b in market.get("outcomes", [])]
            if not normalize_unibet_market(label, outs, roster):
                unmapped.append(label)
    return {
        "url": event.url,
        "name": event.name,
        "market_count": payload.get("market_count"),
        "normalized_keys": len(keys),
        "unmapped_prop_labels": unmapped,
        "playerish_not_prop": playerish_unmapped,
        "sample_labels": [
            m["label"]
            for m in payload.get("markets", [])
            if is_wnba_player_prop_label(str(m.get("label", "")))
        ][:30],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nba", action="store_true")
    parser.add_argument("--wnba", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not args.nba and not args.wnba:
        args.nba = True

    report: dict = {"betclic": [], "unibet": []}
    bc = BetclicBasketballClient()
    ub = UnibetBasketballClient()

    if args.nba:
        nba_bc = bc.list_nba_matches()
        nba_ub = ub.list_nba_events()
        pick_bc = next(
            (m for m in nba_bc if "pistons" in m.slug.lower() and "celtics" in m.slug.lower()),
            nba_bc[0] if nba_bc else None,
        )
        pick_ub = next(
            (e for e in nba_ub if "pistons" in e.name.lower() and "celtics" in e.name.lower()),
            nba_ub[0] if nba_ub else None,
        )
        if pick_bc:
            report["betclic"].append(audit_betclic_match(bc, pick_bc))
        if pick_ub:
            report["unibet"].append(audit_unibet_event(ub, pick_ub))

    if args.wnba:
        wnba_bc = bc.list_wnba_matches()
        wnba_ub = ub.list_wnba_events()
        if wnba_bc:
            report["betclic"].append(audit_betclic_match(bc, wnba_bc[0]))
        if wnba_ub:
            report["unibet"].append(audit_unibet_event(ub, wnba_ub[0]))

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    for book, items in report.items():
        print(f"\n=== {book.upper()} ===")
        for item in items:
            print(json.dumps(item, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
