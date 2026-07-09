"""Debug Unibet tennis JSON-LD events."""

from __future__ import annotations

from unibet_client import UnibetClient


def main() -> None:
    client = UnibetClient()
    for item in client.list_tennis_events_from_json_ld():
        print(item)


if __name__ == "__main__":
    main()
