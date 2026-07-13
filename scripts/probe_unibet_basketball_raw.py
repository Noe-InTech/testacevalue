"""Dump raw Unibet embedded JSON for basketball player props (debug)."""
from __future__ import annotations

import json
import re
import sys

from unibet_basketball_client import UnibetBasketballClient


def main() -> None:
    needle = (sys.argv[1] if len(sys.argv) > 1 else "canada").lower()
    client = UnibetBasketballClient()
    events = client.list_wnba_events()
    ev = next((e for e in events if "dream" in e.name.lower() or "sparks" in e.name.lower()), events[0] if events else None)
    if not ev:
        print("no event")
        return
    print("EVENT", ev.name, ev.url)
    html = client.get_event_html(ev.url)
    print("HTML bytes", len(html))

    for match in re.finditer(r'"marketDesc":"([^"]+)"', html):
        desc = match.group(1)
        if needle not in desc.lower():
            continue
        if "rebond" not in desc.lower() and "rebound" not in desc.lower():
            continue
        start = match.start()
        chunk = html[start : start + 4000]
        print("\n=== MARKET DESC ===")
        print(desc)
        print("--- chunk snippets with price ---")
        for m in re.finditer(
            r'"description":"([^"]{0,80})"[^}{]{0,400}?"price":"([^"]+)"',
            chunk,
            flags=re.I,
        ):
            print(" desc:", m.group(1), "| price:", m.group(2))
        for key in ("europeanPrice", "decimalPrice", "americanPrice", "handicap", "line"):
            if key in chunk:
                print(f" has {key}")
        # try parse object-ish blocks
        for m in re.finditer(r'\{[^{}]{0,500}?"description":"[^"]+"[^{}]{0,500}?\}', chunk):
            blob = m.group(0)
            if "price" in blob.lower() and ("plus" in blob.lower() or "moins" in blob.lower()):
                print(" BLOCK:", blob[:500])

    payload = client.build_event_payload(ev)
    for market in payload["markets"]:
        if needle in market["label"].lower() and "rebond" in market["label"].lower():
            print("\n=== PARSED MARKET ===")
            print(market["label"])
            print(market["outcomes"])


if __name__ == "__main__":
    main()
