"""Probe Winamax tennis page/API structure."""

from __future__ import annotations

import json
import re

import requests

BASE = "https://www.winamax.fr"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
}


def main() -> None:
    session = requests.Session()
    session.headers.update(HEADERS)

    paths = [
        "/paris-sportifs/sports/5",
        "/paris-sportifs/sports/5/1",
        "/paris-sportifs/tennis",
        "/paris-sportifs",
    ]
    for path in paths:
        response = session.get(f"{BASE}{path}", timeout=30)
        print(f"=== {path} status={response.status_code} len={len(response.text)} ===")
        text = response.text
        for pattern in [
            "PRELOADED_STATE",
            "__INITIAL_STATE__",
            "window.__",
            "socket.io",
            "uof-sports",
            '"matches"',
            '"events"',
            "sportId",
            "matchId",
        ]:
            if pattern.lower() in text.lower():
                print(f"  found: {pattern}")

        scripts = re.findall(r"<script[^>]*>(.*?)</script>", text, flags=re.S)
        for index, script in enumerate(scripts):
            script = script.strip()
            if not script.startswith("{"):
                continue
            if len(script) < 500:
                continue
            try:
                payload = json.loads(script)
            except json.JSONDecodeError:
                continue
            print(f"  json script {index} keys={list(payload.keys())[:12]}")

        links = re.findall(r'href="(/paris-sportifs/[^"]+)"', text)
        tennis_links = [link for link in links if "tennis" in link.lower() or re.search(r"/m\d+", link)]
        print(f"  sample links: {tennis_links[:8]}")

    # Try static API endpoints seen in community reverse engineering
    api_paths = [
        "/paris-sportifs/api/sports/5",
        "/paris-sportifs/api/matches",
        "/betting/api/sports/5",
    ]
    for path in api_paths:
        response = session.get(f"{BASE}{path}", timeout=30)
        print(f"API {path} -> {response.status_code} {response.text[:120]!r}")


if __name__ == "__main__":
    main()
