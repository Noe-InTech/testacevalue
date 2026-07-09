"""Probe rapide de l'API et du listing public Unibet tennis."""

from __future__ import annotations

import json

from unibet_client import UnibetClient


def main() -> None:
    client = UnibetClient()

    competitions = client.list_tennis_competitions()
    print(f"competitions={len(competitions)}")
    for item in competitions[:20]:
        print(
            f"- {item.category_name} | {item.competition_name} "
            f"(id={item.competition_id}, events={item.event_count})"
        )

    urls = client.list_tennis_event_urls()
    print(f"\nevent_urls={len(urls)}")
    for url in urls[:20]:
        print("-", url)

    events = client.list_tennis_events_from_json_ld()
    print(f"\njsonld_events={len(events)}")
    for event in events[:10]:
        print(json.dumps(event, ensure_ascii=False))


if __name__ == "__main__":
    main()
