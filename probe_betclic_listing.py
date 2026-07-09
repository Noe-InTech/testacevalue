"""Debug Betclic tennis listing links."""

from __future__ import annotations

import re

import requests

URL = "https://www.betclic.fr/tennis-stennis"


def main() -> None:
    html = requests.get(
        URL,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "fr-FR,fr;q=0.9",
        },
        timeout=30,
    ).text
    print("status len", len(html))
    patterns = [
        r'href="(/tennis-stennis/[^"]+)"',
        r'href="(https://www\.betclic\.fr/tennis-stennis/[^"]+)"',
        r'"/tennis-stennis/[^"]+m\d+[^"]*"',
    ]
    for pattern in patterns:
        matches = sorted(set(re.findall(pattern, html)))
        print(pattern, len(matches))
        for item in matches[:20]:
            print(" ", item[:120])


if __name__ == "__main__":
    main()
