"""Dump FanDuel runner odds structure."""

import json

import requests

AK = "FhMFpcPWXMeyZxOx"
BASE = "https://sbapi.nj.sportsbook.fanduel.com"
PARAMS = {
    "currencyCode": "USD",
    "exchangeLocale": "en_US",
    "includePrices": "true",
    "language": "en",
    "regionCode": "NAMERICA",
    "_ak": AK,
    "eventId": "35800202",
    "tab": "popular",
}


def main() -> None:
    response = requests.get(f"{BASE}/api/event-page", params=PARAMS, timeout=30)
    data = response.json()
    markets = (data.get("attachments") or {}).get("markets") or {}
    for market_id, market in markets.items():
        name = market.get("marketName")
        if name in {"Moneyline", "Match Betting", "Set 1 Winner", "Total Match Games 22.5", "Set Betting"}:
            print("\n===", name, "===")
            for runner in market.get("runners", [])[:4]:
                print(json.dumps(runner, indent=2)[:1200])


if __name__ == "__main__":
    main()
