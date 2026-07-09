"""Extract Betclic JS snippets around API markers."""

from __future__ import annotations

import requests

URL = "https://www.betclic.fr/main-ZXFFKLGK.js"


def snippet(text: str, term: str, radius: int = 600) -> None:
    index = text.find(term)
    print(f"TERM {term} @ {index}")
    if index >= 0:
        print(text[max(0, index - radius) : index + radius])
    print("---")


def main() -> None:
    js = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=60).text
    for term in ("GetMatch", "openMarket", "gordon", "grpc", "aces", "break"):
        snippet(js, term)


if __name__ == "__main__":
    main()
