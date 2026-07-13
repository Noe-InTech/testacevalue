"""Quick Winamax connectivity probe (VM / local)."""

from __future__ import annotations

import sys

from betclic_basketball_client import BetclicBasketballClient
from fanduel_basketball_client import FanDuelBasketballClient
from unibet_basketball_client import UnibetBasketballClient
from winamax_basketball_client import WinamaxBasketballClient
from winamax_client import WinamaxClient


def probe(label: str, callback) -> bool:
    try:
        result = callback()
        if isinstance(result, list):
            print(f"{label}: ok count={len(result)}")
        else:
            print(f"{label}: ok")
        return True
    except Exception as exc:
        print(f"{label}: FAIL {type(exc).__name__}: {exc}")
        return False


def main() -> int:
    ok = True
    ok &= probe(
        "tennis_sport",
        lambda: len((WinamaxClient(fetch_timeout=15).fetch_route("sport:5") or {}).get("matches") or {}),
    )
    ok &= probe("winamax_wnba", lambda: WinamaxBasketballClient(fetch_timeout=25).list_wnba_matches())
    ok &= probe("unibet_wnba", lambda: UnibetBasketballClient().list_wnba_events())
    ok &= probe("betclic_wnba", lambda: BetclicBasketballClient().list_wnba_matches())
    ok &= probe("fanduel_wnba", lambda: FanDuelBasketballClient().list_wnba_events())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
