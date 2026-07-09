"""Probe The Odds API tennis + FanDuel availability."""

from api_client import OddsApiClient
from config import Config


def main() -> None:
    client = OddsApiClient(Config.from_env().api_key)
    sports = client.get_sports(all_sports=True)
    tennis = [s for s in sports if "tennis" in s.get("key", "")]
    print("Tennis sports:")
    for sport in tennis:
        print(f"  {sport['key']}: {sport['title']} active={sport.get('active')}")

    for sport_key in ["tennis_atp", "tennis_wta"]:
        try:
            events = client.get_events(sport_key)
            print(f"\n{sport_key}: {len(events)} events")
            for event in events[:3]:
                print(
                    " ",
                    event.get("id"),
                    event.get("home_team"),
                    "vs",
                    event.get("away_team"),
                    event.get("commence_time"),
                )
            if events:
                markets = client.get_event_markets(sport_key, events[0]["id"], ["fanduel"])
                keys = []
                for bm in markets.get("bookmakers", []):
                    keys = [m["key"] for m in bm.get("markets", [])]
                print("  FanDuel markets sample:", keys[:20], f"({len(keys)} total)")
        except Exception as exc:
            print(f"\n{sport_key}: ERROR {exc}")

    print("\nQuota:", client.last_quota)


if __name__ == "__main__":
    main()
