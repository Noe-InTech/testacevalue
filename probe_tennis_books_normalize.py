"""Debug normalization for one tennis match."""

from __future__ import annotations

import json

from betclic_client import BetclicClient
from tennis_books_mapping import normalize_betclic_market, normalize_unibet_market
from unibet_client import UnibetClient

UNIBET_URL = "https://www.unibet.fr/paris-tennis/atp/wimbledon-h/3363472/j-sinner-vs-n-djokovic"
BETCLIC_URL = (
    "https://www.betclic.fr/tennis-stennis/wimbledon-h-c24/"
    "jannik-sinner-novak-djokovic-m1163187647176704"
)


def dump(book: str, markets: list) -> None:
    print(f"\n== {book} normalized ==")
    for item in markets:
        print(item.compare_key, {outcome.label: outcome.odds for outcome in item.outcomes})


def main() -> None:
    unibet = UnibetClient()
    betclic = BetclicClient()

    u_event = unibet.build_event_payload(
        {
            "url": UNIBET_URL,
            "home": "J.Sinner",
            "away": "N.Djokovic",
            "name": "J.Sinner vs N.Djokovic",
        }
    )
    b_event = betclic.build_event_payload(BETCLIC_URL)

    print("unibet markets", len(u_event["markets"]))
    for market in u_event["markets"][:8]:
        print(" U", market["label"])

    print("betclic markets", len(b_event["markets"]))
    for market in b_event["markets"]:
        print(" B", market["label"])

    u_norm = []
    for market in u_event["markets"]:
        u_norm.extend(
            normalize_unibet_market(
                market["label"],
                market["outcomes"],
                u_event["home_player"],
                u_event["away_player"],
            )
        )
    b_norm = []
    for market in b_event["markets"]:
        b_norm.extend(
            normalize_betclic_market(
                market["label"],
                market["outcomes"],
                b_event["home_player"],
                b_event["away_player"],
            )
        )

    dump("unibet", u_norm)
    dump("betclic", b_norm)

    u_keys = {item.compare_key for item in u_norm}
    b_keys = {item.compare_key for item in b_norm}
    print("\nintersection", sorted(u_keys & b_keys))
    print("unibet only", sorted(u_keys - b_keys))
    print("betclic only", sorted(b_keys - u_keys))


if __name__ == "__main__":
    main()
