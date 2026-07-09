"""Dump Betclic grpc ng-state match payload."""

from __future__ import annotations

import json
from pathlib import Path

from betclic_client import BetclicClient

URL = (
    "https://www.betclic.fr/tennis-stennis/wimbledon-h-c24/"
    "jannik-sinner-novak-djokovic-m1163187647176704"
)


def main() -> None:
    client = BetclicClient()
    html = client.session.get(URL, timeout=30).text
    ng = client.extract_ng_state(html)
    payload = ng.get("grpc:1786868347", {}).get("response", {}).get("payload", {})
    out = Path("output/betclic_match_grpc_payload.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("written", out)
    match = payload.get("match") or {}
    print("match keys", list(match.keys())[:20])
    subs = match.get("subCategories") or match.get("sub_categories") or []
    print("subCategories", len(subs))
    for sub in subs[:5]:
        print(" sub", sub.get("name"), "markets", len(sub.get("markets") or []))
    top = payload.get("topMycombis") or payload.get("top_mycombis") or []
    print("topMycombis", len(top))
    for item in top[:3]:
        print(" combo", item.get("marketName"), item.get("openMarketCount"))


if __name__ == "__main__":
    main()
