"""Probe Betclic tennis match URLs and market markers."""

from __future__ import annotations

import re

from betclic_client import BetclicClient


def main() -> None:
    client = BetclicClient()
    html = client.get_page_html("/tennis-stennis")
    links = sorted(set(re.findall(r'href="(/tennis-stennis/[^"]+)"', html)))
    print(f"links={len(links)}")
    for link in links[:30]:
        print(link)

    for link in links:
        if link.count("/") < 4:
            continue
        url = f"{client.base_url}{link}"
        page = client.session.get(url, timeout=30)
        text = page.text.lower()
        if any(term in text for term in ("break", "ace", "tie-break", "tie break")):
            print("interesting", page.status_code, url)
            for term in ("break", "ace", "tie-break"):
                if term in text:
                    print(" ", term, "found")


if __name__ == "__main__":
    main()
