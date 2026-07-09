"""Inspect Betclic transport config and auth flow."""

from __future__ import annotations

import re

import requests

HTML_URL = "https://www.betclic.fr/tennis-stennis/wimbledon-h-c24/jannik-sinner-novak-djokovic-m1163187647176704"
JS_URL = "https://www.betclic.fr/main-ZXFFKLGK.js"


def print_snippet(text: str, term: str, radius: int = 1200) -> None:
    index = text.find(term)
    print(f"\nTERM {term} @ {index}")
    if index >= 0:
        print(text[max(0, index - radius) : index + radius])
    print("---")


def main() -> None:
    html = requests.get(HTML_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30).text
    js = requests.get(JS_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=60).text

    print("HTML begmedia urls")
    for item in sorted(set(re.findall(r"https://[^\" ]+begmedia\.com", html))):
        print(" ", item)

    print("HTML key terms")
    for term in ("grpcGordonTier1Url", "grpcGordonTier2Url", "grpcGordonTier3Url", "apif.begmedia.com"):
        print_snippet(html, term, radius=500)

    print("JS key terms")
    for term in (
        "addAuthHeader(o){",
        "performHandshake(e){",
        "/kong/api/v3/handshake",
        "grpcGordonTier2Url",
        "grpcGordonTier3Url",
        "getAppSetting(`grpcGordonTier2Url`)",
    ):
        print_snippet(js, term)


if __name__ == "__main__":
    main()
