"""Inspect Betclic JS for Gordon/Offering service names."""

from __future__ import annotations

import re

import requests

URL = "https://www.betclic.fr/main-ZXFFKLGK.js"


def print_snippets(js: str, term: str, radius: int = 1200) -> None:
    start = 0
    seen = 0
    while True:
        index = js.find(term, start)
        if index < 0:
            break
        print(f"\nTERM {term} @ {index}")
        print(js[max(0, index - radius) : index + radius])
        print("---")
        start = index + len(term)
        seen += 1
        if seen >= 3:
            break


def main() -> None:
    js = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=60).text

    service_matches = sorted(set(re.findall(r"offering\.access\.api\.[A-Za-z0-9_]+Service", js)))
    print("service names", len(service_matches))
    for item in service_matches[:50]:
        print(" ", item)

    for term in (
        "GetMatchRequest",
        "GetMatchResponse",
        "GetMatchBySportRequest",
        "GetMatchesByMultiCompetitionsRequest",
        "supported_features",
        "match_id",
        "offering.access.api.",
        "new G$16(`offering.access.api.",
        "name:`GetMatch`",
    ):
        print_snippets(js, term)


if __name__ == "__main__":
    main()
