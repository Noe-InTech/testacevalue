"""List Betclic ng-state keys with market-rich payloads."""

from __future__ import annotations

import json
import re

from betclic_client import BetclicClient

URL = (
    "https://www.betclic.fr/tennis-stennis/wimbledon-h-c24/"
    "jannik-sinner-novak-djokovic-m1163187647176704"
)


def main() -> None:
    client = BetclicClient()
    html = client.session.get(URL, timeout=30).text
    ng = client.extract_ng_state(html)
    for key, value in ng.items():
        blob = json.dumps(value, ensure_ascii=False)
        market_names = set(re.findall(r'"marketName":"([^"]+)"', blob))
        if len(market_names) >= 3:
            print("KEY", key, "markets", len(market_names))
            for name in sorted(market_names):
                if any(t in name.lower() for t in ("ace", "break", "tie", "service")):
                    print(" *", name)
            print(" sample:", sorted(market_names)[:15])

    gordon = sorted(set(re.findall(r"https://gordon[^\"\\]+", html)))
    apif = sorted(set(re.findall(r"https://apif[^\"\\]+", html)))
    print("gordon urls", gordon[:10])
    print("apif urls", apif[:10])


if __name__ == "__main__":
    main()
