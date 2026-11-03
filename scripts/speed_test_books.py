#!/usr/bin/env python3
"""Mesure les temps listing (parallèle NBA + Winamax tennis)."""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fanduel_basketball_client import FanDuelBasketballClient
from unibet_basketball_client import UnibetBasketballClient
from winamax_basketball_client import WinamaxBasketballClient
from winamax_client import WinamaxClient


def timed(label: str, fn):
    t0 = time.perf_counter()
    err = None
    count = 0
    try:
        out = fn()
        count = len(out) if out is not None else 0
    except Exception as exc:
        err = str(exc)[:160]
    dt = time.perf_counter() - t0
    return {"book": label, "seconds": round(dt, 2), "count": count, "error": err}


def main() -> None:
    host = sys.argv[1] if len(sys.argv) > 1 else "local"
    w = WinamaxBasketballClient(fetch_timeout=25)
    results: dict[str, object] = {"host": host, "tests": []}

    t0 = time.perf_counter()
    with ThreadPoolExecutor(3) as pool:
        futs = [
            pool.submit(timed, "Unibet_NBA", UnibetBasketballClient().list_nba_events),
            pool.submit(timed, "Winamax_NBA", w.list_nba_matches),
            pool.submit(timed, "FanDuel_NBA", FanDuelBasketballClient().list_nba_events),
        ]
        parallel = [f.result() for f in futs]
    results["tests"].append(
        {
            "name": "nba_calendar_parallel",
            "wall_seconds": round(time.perf_counter() - t0, 2),
            "legs": parallel,
        }
    )

    results["tests"].append(timed("Winamax_tennis", WinamaxClient().list_singles_tennis_matches))
    def winamax_sport2():
        payload = w.fetch_route("sport:2")
        return list((payload or {}).get("matches") or {})

    results["tests"].append(timed("Winamax_sport2_matches", winamax_sport2))

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
