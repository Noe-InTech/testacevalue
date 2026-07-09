"""Find GetMatch service path in Betclic JS."""

from __future__ import annotations

import re

import requests

URL = "https://www.betclic.fr/main-ZXFFKLGK.js"


def main() -> None:
    js = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=60).text
    for pattern in (
        r"offering\.access\.api\.[A-Za-z0-9_]+",
        r"GetMatch[A-Za-z]*",
        r"gordon[^`\"']{0,80}",
        r"/offering[^\"']+",
    ):
        matches = sorted(set(re.findall(pattern, js)))
        print(pattern, len(matches))
        for item in matches[:15]:
            print(" ", item[:120])


if __name__ == "__main__":
    main()
