"""Probe FanDuel internal API for tennis."""

import json
import re

import requests

AK = "FhMFpcPWXMeyZxOx"
BASE_PARAMS = {
    "currencyCode": "USD",
    "exchangeLocale": "en_US",
    "includePrices": "true",
    "language": "en",
    "regionCode": "NAMERICA",
    "_ak": AK,
}


def fetch_json(url: str, params: dict | None = None) -> dict:
    response = requests.get(
        url,
        params=params,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    print(url, response.status_code, len(response.text))
    if response.status_code != 200:
        print(response.text[:300])
        return {}
    return response.json()


def main() -> None:
    hosts = [
        "https://sbapi.nj.sportsbook.fanduel.com",
        "https://sbapi.pa.sportsbook.fanduel.com",
        "https://sbapi.il.sportsbook.fanduel.com",
    ]
    page_ids = ["tennis", "wimbledon", "tennis-in-play", "atp", "wta"]

    for host in hosts:
        for page_id in page_ids:
            data = fetch_json(
                f"{host}/api/content-managed-page",
                {
                    **BASE_PARAMS,
                    "page": "CUSTOM",
                    "customPageId": page_id,
                },
            )
            if not data:
                continue
            attachments = data.get("attachments") or {}
            events = attachments.get("events") or {}
            markets = attachments.get("markets") or {}
            print(f"  page={page_id} events={len(events)} markets={len(markets)}")
            for event_id, event in list(events.items())[:5]:
                name = event.get("name")
                print("   event", event_id, name, event.get("openDate"))

    # try discover page ids from tennis landing
    landing = requests.get(
        "https://sportsbook.fanduel.com/navigation/tennis",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    print("\nnavigation", landing.status_code)
    ids = sorted(set(re.findall(r"customPageId=([a-z0-9\-]+)", landing.text)))
    print("customPageIds", ids[:30])

    # if we found events above, probe one event-page
    host = hosts[0]
    data = fetch_json(
        f"{host}/api/content-managed-page",
        {**BASE_PARAMS, "page": "CUSTOM", "customPageId": "wimbledon"},
    )
    events = (data.get("attachments") or {}).get("events") or {}
    if events:
        # pick a singles match if possible
        chosen = None
        for event_id, event in events.items():
            name = event.get("name", "")
            if " v " in name and "/" not in name:
                chosen = (event_id, name)
                break
        if not chosen:
            event_id = next(iter(events))
            chosen = (event_id, events[event_id].get("name"))
        event_id, event_name = chosen
        print("\nProbing event", event_id, event_name)
        for tab in ("popular", "all-markets", "set-betting", "game-lines", "same-game-parlay-"):
            event_data = fetch_json(
                f"{host}/api/event-page",
                {
                    **BASE_PARAMS,
                    "eventId": event_id,
                    "tab": tab,
                },
            )
            markets = (event_data.get("attachments") or {}).get("markets") or {}
            print(f"  tab={tab} markets={len(markets)}")
            for market_id, market in list(markets.items())[:12]:
                runners = market.get("runners") or []
                sample = []
                for runner in runners[:3]:
                    odds = (runner.get("winRunnerOdds") or {}).get("decimalDisplayOdds") or {}
                    dec = odds.get("decimalOdds")
                    sample.append(f"{runner.get('runnerName')}={dec}")
                print("   ", market.get("marketName"), "|", ", ".join(sample))


if __name__ == "__main__":
    main()
