"""Probe a Coteur tennis match markets."""

import json

from coteur_client import CoteurClient


def probe_match(renc_id: int) -> None:
    client = CoteurClient()
    data = client.get_full_odds(renc_id)
    info = data.get("info") or {}
    print("renc_id", renc_id)
    print("sport", (info.get("sport") or {}).get("sportNom"))
    print("comp", (info.get("competition") or {}).get("competitionNom"))
    print(
        "players",
        (info.get("teamDom") or {}).get("equipeNom"),
        "vs",
        (info.get("teamExt") or {}).get("equipeNom"),
    )
    odds = data.get("odds") or []
    print("markets", len(odds))
    for entry in odds:
        print(" ", entry.get("typename"), repr(entry.get("special") or ""))


def main() -> None:
    for renc_id in (1596979, 1596959):
        print("=" * 60)
        probe_match(renc_id)


if __name__ == "__main__":
    main()
