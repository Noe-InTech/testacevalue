"""Discover Coteur API endpoints for tennis match listing."""

import json
import re

import requests

from coteur_client import CoteurClient


def try_url(url: str) -> None:
    response = requests.get(
        url,
        headers={"X-Requested-With": "XMLHttpRequest", "User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    print(url, response.status_code, response.headers.get("content-type", ""), len(response.text))
    if response.status_code == 200 and "json" in response.headers.get("content-type", ""):
        data = response.json()
        if isinstance(data, list):
            print("  list len", len(data))
            if data:
                print("  sample keys", list(data[0].keys())[:15] if isinstance(data[0], dict) else data[0])
        elif isinstance(data, dict):
            print("  keys", list(data.keys())[:20])


def main() -> None:
    client = CoteurClient()
    candidates = [
        "https://www.coteur.com/api/sports",
        "https://www.coteur.com/api/sport/tennis",
        "https://www.coteur.com/api/competitions/tennis",
        "https://www.coteur.com/api/renc/search?sport=tennis",
        "https://www.coteur.com/api/renc/upcoming",
        "https://www.coteur.com/api/renc/live",
        "https://www.coteur.com/cotes/tennis/wimbledon-simples-hommes",
        "https://www.coteur.com/cotes/tennis/wimbledon-simples-hommes-2026",
        "https://www.coteur.com/cotes/tennis/atp/wimbledon",
    ]
    for url in candidates:
        try_url(url)

    for url in candidates[-3:]:
        if "cotes/" in url:
            response = client.session.get(url, timeout=30)
            print("\npage", url, response.status_code)
            if response.status_code == 200:
                links = re.findall(r'href="(/cote/[^"]+)"', response.text)
                print(" matches", len(links))
                for link in links[:10]:
                    print("  ", link)


if __name__ == "__main__":
    main()
