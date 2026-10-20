"""Vérifie qu'un JSON latest_nba contient des cotes Betclic (by_book ou FR seul)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "runner" / "data" / "latest_nba.json"
    if not path.is_file():
        print(f"missing {path}")
        return 2
    payload = json.loads(path.read_text(encoding="utf-8"))
    counts = payload.get("fr_books_row_counts") or {}
    betclic = int(counts.get("Betclic") or 0)
    notes = [str(n) for n in (payload.get("notes") or []) if "Betclic" in str(n)]
    print("comparable_count", payload.get("comparable_count"))
    print("fr_only_count", payload.get("fr_only_count"))
    print("fr_books_row_counts", counts)
    if notes:
        print("notes_betclic", notes[:3])
    for row in (payload.get("match_progress") or [])[:5]:
        print(
            "match",
            row.get("match"),
            "fr_books_scraped",
            row.get("fr_books_scraped"),
        )
    if betclic <= 0:
        print("FAIL: no Betclic lines in fr_books_row_counts")
        return 1
    print("OK: Betclic present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
