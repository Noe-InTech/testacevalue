"""Search Betclic JS for Gordon Sync GetMatch usage."""

from __future__ import annotations

import requests

URL = "https://www.betclic.fr/main-ZXFFKLGK.js"


def main() -> None:
    js = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=60).text
    term = "GetMatchRequest"
    index = js.find(term)
    while index >= 0:
        print(js[max(0, index - 400) : index + 800])
        print("---")
        index = js.find(term, index + 1)
        if index > 0 and js.count(term) > 5:
            break


if __name__ == "__main__":
    main()
