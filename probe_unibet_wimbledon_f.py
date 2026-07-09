"""Deep search Unibet Wimbledon F HTML for events."""

from __future__ import annotations

import re

from unibet_client import UnibetClient


def main() -> None:
    client = UnibetClient()
    html = client.get_tennis_listing_html("/paris-tennis/wta/wimbledon-f")
    print("muchova", "muchova" in html.lower())
    print("gauff", "gauff" in html.lower())

    for script_id in ("sport-main-jsonLd", "sport-jsonLd", "jsonLd"):
        match = re.search(
            rf'<script id="{script_id}" type="application/ld\+json">(.*?)</script>',
            html,
            flags=re.S,
        )
        if match:
            body = match.group(1)
            print(f"script {script_id} len={len(body)}")
            if "muchova" in body.lower() or "gauff" in body.lower():
                print(body[:800])

    links = re.findall(r'href="(/paris-tennis/[^"]+)"', html)
    wta_links = [link for link in links if "/wta/wimbledon-f/" in link]
    print(f"wta wimbledon-f links: {len(wta_links)}")
    for link in wta_links[:10]:
        print(" ", link)
    for link in wta_links:
        if "muchova" in link.lower() or "gauff" in link.lower():
            print("MATCH", link)

    # generic event cards in HTML
    cards = re.findall(r'data-event-id="(\d+)"[^>]*data-event-name="([^"]+)"', html)
    print(f"data-event cards: {len(cards)}")
    for event_id, name in cards[:15]:
        print(event_id, name)
    for event_id, name in cards:
        if "muchova" in name.lower() or "gauff" in name.lower():
            print("CARD MATCH", event_id, name)


if __name__ == "__main__":
    main()
