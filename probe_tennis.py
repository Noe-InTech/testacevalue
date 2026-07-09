"""Probe Coteur tennis structure and sample match odds."""

import json
import re

from coteur_client import CoteurClient


def main() -> None:
    client = CoteurClient()
    homepage = client.session.get("https://www.coteur.com/", timeout=30)
    print("homepage", homepage.status_code)
    tennis_links = sorted(
        set(
            re.findall(r'href="(/cotes/[^"]*tennis[^"]*)"', homepage.text, flags=re.I)
            + re.findall(r'href="(/cote/[^"]+)"', homepage.text)
        )
    )
    print("links from homepage:", len(tennis_links))
    for link in tennis_links[:30]:
        print(" ", link)

    candidate_pages = [
        "https://www.coteur.com/",
    ]
    for link in tennis_links:
        if link.startswith("/cotes/"):
            candidate_pages.append(f"https://www.coteur.com{link}")

    all_matches = []
    for url in candidate_pages:
        response = client.session.get(url, timeout=30)
        if response.status_code != 200:
            print("skip", url, response.status_code)
            continue
        matches = client.list_matches_from_competition_page(url)
        print(url, "->", len(matches), "matches")
        all_matches.extend(matches)

    seen = set()
    unique = []
    for match in all_matches:
        if match["renc_id"] not in seen:
            seen.add(match["renc_id"])
            unique.append(match)

    print("\nUnique matches:", len(unique))
    for match in unique[:10]:
        print(" ", match)

    if unique:
        renc_id = unique[0]["renc_id"]
        data = client.get_full_odds(renc_id)
        info = data.get("info") or {}
        print("\nSample match", renc_id)
        print(" sport:", (info.get("sport") or {}).get("sportNom"))
        print(
            " players:",
            (info.get("teamDom") or {}).get("equipeNom"),
            "vs",
            (info.get("teamExt") or {}).get("equipeNom"),
        )
        odds = data.get("odds") or []
        print(" market types:", sorted({o.get("typename") for o in odds}))
        print(" total markets:", len(odds))
        if odds:
            first = odds[0]
            md = client.get_market_odds(renc_id, first["typename"], first.get("special") or "")
            print(" first market:", first["typename"], first.get("special"))
            print(" sample odds:", json.dumps(md, indent=2)[:2000])


if __name__ == "__main__":
    main()
