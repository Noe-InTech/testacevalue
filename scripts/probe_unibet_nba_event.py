"""Diagnostic Unibet NBA — listing + marchés props sur un match."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from basketball_books_mapping import is_wnba_player_prop_label, normalize_unibet_market
from compare_wnba_props_vs_fanduel import count_normalized_fr_outcomes_for_event
from unibet_basketball_client import UnibetBasketballClient


def main() -> None:
    needle = (sys.argv[1] if len(sys.argv) > 1 else "wizards").strip().lower()
    client = UnibetBasketballClient()
    events = client.list_nba_events()
    print("nba_events", len(events))
    event = next(
        (
            e
            for e in events
            if needle in e.home_team.lower()
            or needle in e.away_team.lower()
            or needle in e.url.lower()
        ),
        events[0] if events else None,
    )
    if event is None:
        print("no event")
        return
    print("match", event.name, event.url)
    payload = client.build_event_payload(event)
    markets = payload.get("markets") or []
    print("market_count", payload.get("market_count"), "raw", len(markets))
    roster = payload.get("roster") or []
    print("roster_size", len(roster))
    prop_markets = [m for m in markets if is_wnba_player_prop_label(str(m.get("label", "")))]
    print("prop_markets", len(prop_markets))
    for m in prop_markets[:8]:
        label = str(m.get("label", ""))
        outcomes = [(str(a), b) for a, b in m.get("outcomes") or []]
        norm = normalize_unibet_market(label, outcomes, roster)
        print(" ", label[:90], "| outcomes", len(outcomes), "| norm", len(norm))
    norm_total = count_normalized_fr_outcomes_for_event("unibet", payload, roster=roster)
    print("normalized_outcomes", norm_total)


if __name__ == "__main__":
    main()
