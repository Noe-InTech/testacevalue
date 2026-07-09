"""Parse Coteur ATP Wimbledon page links."""

import re

from coteur_client import CoteurClient


def main() -> None:
    client = CoteurClient()
    url = "https://www.coteur.com/cotes/tennis/atp/wimbledon"
    response = client.session.get(url, timeout=30)
    print("status", response.status_code, "len", len(response.text))
    patterns = [
        r'href="(/cote/[^"]+)"',
        r'href="(/cotes/[^"]+)"',
        r'data-url="([^"]+)"',
        r'rencId["\']?\s*[:=]\s*(\d+)',
    ]
    for pattern in patterns:
        found = re.findall(pattern, response.text)
        print(pattern, len(found))
        for item in found[:15]:
            print(" ", item)

    matches = client.list_matches_from_competition_page(url)
    print("list_matches_from_competition_page", len(matches))
    for match in matches[:20]:
        print(match)


if __name__ == "__main__":
    main()
