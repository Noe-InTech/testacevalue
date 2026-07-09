"""Probe des marchés SSR Unibet sur une page match tennis."""

from __future__ import annotations

from unibet_client import UnibetClient


def main() -> None:
    client = UnibetClient()
    event_url = "https://www.unibet.fr/paris-tennis/atp/wimbledon-h/3363472/j-sinner-vs-n-djokovic"
    markets = client.get_event_markets(event_url)
    print(f"markets={len(markets)}")

    interesting_terms = ("aces", "break", "tie-break", "service", "double faute", "performance")
    for market in markets:
        label_lower = market.label.lower()
        if any(term in label_lower for term in interesting_terms):
            print(f"\n{market.label}")
            for outcome in market.outcomes[:12]:
                print(f"  - {outcome.label} => {outcome.odds}")


if __name__ == "__main__":
    main()
