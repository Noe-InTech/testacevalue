"""Find market structures in Betclic ng-state."""

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
        if "marketName" in blob or "selections" in blob:
            print("KEY", key, "len", len(blob))
            names = re.findall(r'"marketName":"([^"]+)"', blob)
            print("names", sorted(set(names))[:40])

    # embedded in HTML outside ng-state
    names = re.findall(r'"marketName":"([^"]+)"', html)
    print("html names", sorted(set(names)))


if __name__ == "__main__":
    main()
