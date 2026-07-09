"""Try Coteur URL patterns for Wimbledon listing."""

import re

from coteur_client import CoteurClient


URLS = [
    "https://www.coteur.com/cotes/monde/wimbledon-simples-hommes",
    "https://www.coteur.com/cotes/tennis/monde/wimbledon-simples-hommes",
    "https://www.coteur.com/cotes/tennis/wimbledon-simples-hommes",
    "https://www.coteur.com/cotes/tennis/atp/wimbledon-simples-hommes",
    "https://www.coteur.com/cotes/tennis/wta/wimbledon",
    "https://www.coteur.com/cotes/tennis/wta/wimbledon-simples-dames",
    "https://www.coteur.com/cotes/tennis/atp",
    "https://www.coteur.com/cotes/tennis/wta",
    "https://www.coteur.com/sitemap.xml",
]


def main() -> None:
    client = CoteurClient()
    for url in URLS:
        response = client.session.get(url, timeout=30)
        print(url, response.status_code)
        if response.status_code != 200:
            continue
        if url.endswith("sitemap.xml"):
            tennis = [line for line in response.text.splitlines() if "tennis" in line.lower() or "wimbledon" in line.lower()]
            print(" sitemap tennis lines", len(tennis))
            for line in tennis[:20]:
                print("  ", line.strip())
            continue
        matches = re.findall(r'href="(/cote/[^"]+)"', response.text)
        print(" matches", len(matches))
        for link in matches[:8]:
            print("  ", link)


if __name__ == "__main__":
    main()
