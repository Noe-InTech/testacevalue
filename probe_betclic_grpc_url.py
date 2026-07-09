"""Inspect Betclic grpc-web URL construction."""

from __future__ import annotations

import requests

URL = "https://www.betclic.fr/main-ZXFFKLGK.js"


def print_snippet(js: str, term: str, radius: int = 1600) -> None:
    index = js.find(term)
    print(f"\nTERM {term} @ {index}")
    if index >= 0:
        print(js[max(0, index - radius) : index + radius])
    print("---")


def main() -> None:
    js = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=60).text
    for term in (
        "localName=",
        "serviceName",
        "methodName",
        "baseUrl",
        "fetch(",
        "url:",
        "pathname",
        "mergeOptions(",
        "serverStreaming(",
        "unary(",
        "transport",
        ".service.typeName",
        ".localName",
    ):
        print_snippet(js, term)


if __name__ == "__main__":
    main()
