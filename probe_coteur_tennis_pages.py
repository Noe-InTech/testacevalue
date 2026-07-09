"""Find Coteur tennis competition pages and matches."""

import re

from coteur_client import CoteurClient


def crawl(start_urls: list[str]) -> tuple[list[str], list[dict]]:
    client = CoteurClient()
    comp_pages: set[str] = set()
    matches: dict[int, dict] = {}

    queue = list(start_urls)
    seen_pages: set[str] = set()

    while queue:
        url = queue.pop(0)
        if url in seen_pages:
            continue
        seen_pages.add(url)

        response = client.session.get(url, timeout=30)
        if response.status_code != 200:
            print("skip", url, response.status_code)
            continue

        for link in re.findall(r'href="(/cotes/[^"]+)"', response.text):
            full = f"https://www.coteur.com{link}"
            if full not in seen_pages and "tennis" in link.lower() or "wimbledon" in link.lower():
                comp_pages.add(full)
                queue.append(full)

        for match in client.list_matches_from_competition_page(url):
            matches[match["renc_id"]] = match

        print(url, "matches", len(matches))

    return sorted(comp_pages), list(matches.values())


def main() -> None:
    comp_pages, matches = crawl(
        [
            "https://www.coteur.com/",
            "https://www.coteur.com/cotes/tennis/wimbledon-2026",
            "https://www.coteur.com/cotes/tennis/wimbledon",
        ]
    )
    print("\nCompetition pages:", len(comp_pages))
    for page in comp_pages[:20]:
        print(" ", page)
    print("\nMatches:", len(matches))
    for match in matches:
        info = f"{match['slug']} ({match['renc_id']})"
        print(" ", info)


if __name__ == "__main__":
    main()
