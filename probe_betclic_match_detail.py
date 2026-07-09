"""Probe Betclic match page market extraction."""

from __future__ import annotations

import re

from betclic_client import BetclicClient

URL = (
    "https://www.betclic.fr/tennis-stennis/wimbledon-h-c24/"
    "jannik-sinner-novak-djokovic-m1163187647176704"
)


def main() -> None:
    client = BetclicClient()
    response = client.session.get(URL, timeout=30)
    html = response.text
    print("status", response.status_code, "len", len(html))
    for term in ("Aces", "aces", "Break", "break", "Tie-break", "tie-break", "ng-state"):
        print(term, html.find(term))

    ng = client.extract_ng_state(html)
    print("ng_keys", len(ng))
    for key, value in ng.items():
        if not isinstance(value, dict):
            continue
        body = value.get("b") or value.get("response", {}).get("payload")
        if body is None:
            continue
        text = str(body).lower()
        if any(t in text for t in ("ace", "break", "tie")):
            print("key", key, "snippet", str(body)[:500])

    # try common betclic market patterns in HTML
    labels = re.findall(r'marketName["\']?\s*:\s*["\']([^"\']+)', html)
    print("marketName count", len(labels))
    for label in labels[:30]:
        print(" ", label)


if __name__ == "__main__":
    main()
