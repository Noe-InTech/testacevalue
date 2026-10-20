"""Dump all Betclic basketball markets (SSR + gRPC) for one NBA match."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from basketball_books_mapping import is_wnba_player_prop_label, normalize_betclic_market
from basketball_constants import BETCLIC_BASKETBALL_GRPC_CATEGORIES
from betclic_basketball_client import BetclicBasketballClient
from betclic_client import BetclicClient


def main() -> None:
    bc = BetclicBasketballClient()
    raw = BetclicClient()
    links = bc.list_nba_matches()
    print("nba_links", len(links))
    link = next(
        (m for m in links if "pistons" in m.slug and "celtics" in m.slug),
        links[0] if links else None,
    )
    if not link:
        print("no link")
        return
    print("url", link.url)

    base = raw.get_match_payload(link.url)
    match = base.get("match") or {}
    cat_ids = [str(c.get("id", "")) for c in (match.get("categories") or []) if c.get("id")]
    print("match_categories", cat_ids)

    ssr = raw.extract_markets_from_match_payload(base)
    print("\n=== SSR only", len(ssr), "markets ===")
    for m in ssr:
        low = m.label.lower()
        if any(x in low for x in ("joueur", "performance", "rebond", "passe", "3 point", "double")):
            print(m.label[:110], "|", len(m.outcomes), "|", (m.outcomes[0].label[:60] if m.outcomes else ""))

    for cat in cat_ids:
        if not cat.startswith("ca_bkb"):
            continue
        pl = raw.fetch_grpc_match_payload(link.url, category_id=cat)
        if not pl:
            print(f"\n=== {cat} EMPTY ===")
            continue
        ms = raw.extract_markets_from_match_payload(pl)
        print(f"\n=== gRPC {cat} : {len(ms)} markets ===")
        for m in ms:
            print(m.label[:110], "|", len(m.outcomes), "|", (m.outcomes[0].label[:60] if m.outcomes else ""))

    payload = bc.build_event_payload(link)
    roster = payload.get("roster") or []
    print("\n=== MERGED build_event_payload", payload["market_count"], "roster", len(roster), "===")
    norm_total = 0
    unmapped: list[str] = []
    for item in payload.get("markets", []):
        label = str(item.get("label", ""))
        if not is_wnba_player_prop_label(label):
            continue
        outs = [(str(a), b) for a, b in item.get("outcomes", [])]
        norm = normalize_betclic_market(label, outs, roster)
        if norm:
            norm_total += len(norm)
        else:
            unmapped.append(label)
        print(label[:100], "->", len(norm), "norm", "outs_sample", outs[:2])
    print("norm_total", norm_total, "unmapped", unmapped)


if __name__ == "__main__":
    main()
