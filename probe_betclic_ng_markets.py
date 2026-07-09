"""Inspect Betclic ng-state for match markets."""

from __future__ import annotations

import json

from betclic_client import BetclicClient

URL = (
    "https://www.betclic.fr/tennis-stennis/wimbledon-h-c24/"
    "jannik-sinner-novak-djokovic-m1163187647176704"
)


def walk(obj, path=""):
    if isinstance(obj, dict):
        keys = set(obj.keys())
        if {"marketName", "selections"} <= keys or {"markets", "matchId"} <= keys:
            print("PATH", path, "keys", list(keys)[:20])
            print(json.dumps(obj, ensure_ascii=False)[:2000])
            print("---")
        for key, value in obj.items():
            walk(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for index, value in enumerate(obj[:50]):
            walk(value, f"{path}[{index}]")


def main() -> None:
    client = BetclicClient()
    html = client.session.get(URL, timeout=30).text
    ng = client.extract_ng_state(html)
    for key, value in ng.items():
        if not isinstance(value, dict):
            continue
        body = value.get("b")
        if body is None:
            continue
        text = json.dumps(body, ensure_ascii=False).lower()
        if "sinner" in text and ("market" in text or "selection" in text):
            print("KEY", key)
            walk(body, key)


if __name__ == "__main__":
    main()
