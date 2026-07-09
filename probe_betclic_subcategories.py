"""Search Betclic ng-state for subCategories/markets."""

from __future__ import annotations

import json

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
        if "subCategories" in blob or "sub_categories" in blob:
            print("KEY", key, "has subCategories")
        if '"markets"' in blob and "1163187647176704" in blob:
            print("KEY", key, "has markets for match")
            if "break" in blob.lower() or "ace" in blob.lower():
                print("  advanced terms found")

    # app settings for gordon url
    for key, value in ng.items():
        if not isinstance(value, dict):
            continue
        body = value.get("b")
        if isinstance(body, dict) and "grpcGordonTier2Url" in body:
            print("gordon urls", body)


if __name__ == "__main__":
    main()
