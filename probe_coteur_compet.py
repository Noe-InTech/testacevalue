"""Bruteforce likely Coteur competition endpoints."""

import requests

from coteur_client import CoteurClient, generate_token


def get(url: str, **kwargs) -> None:
    response = requests.get(url, timeout=30, **kwargs)
    ctype = response.headers.get("content-type", "")
    print(url, response.status_code, ctype[:40], len(response.text))
    if response.status_code == 200 and "json" in ctype:
        print(" ", str(response.json())[:300])


def main() -> None:
    token = generate_token()
    headers = {"token": token}
    compet_id = 7101
    sport_id = 5
    candidates = [
        f"https://oddsv2.coteur.com/odds/getCompetOdds/{compet_id}",
        f"https://oddsv2.coteur.com/odds/getCompetition/{compet_id}",
        f"https://oddsv2.coteur.com/odds/getMatches/{compet_id}",
        f"https://oddsv2.coteur.com/odds/getSportOdds/{sport_id}",
        f"https://www.coteur.com/api/compet/{compet_id}",
        f"https://www.coteur.com/api/compet/{compet_id}/matches",
        f"https://www.coteur.com/api/competition/{compet_id}",
        f"https://www.coteur.com/api/competition/{compet_id}/renc",
        f"https://www.coteur.com/api/sport/{sport_id}/matches",
        f"https://www.coteur.com/api/sport/{sport_id}/competitions",
    ]
    for url in candidates:
        get(url, headers=headers if "oddsv2" in url else {"X-Requested-With": "XMLHttpRequest"})

    client = CoteurClient()
    page = client.session.get("https://www.coteur.com/cotes/tennis/atp/wimbledon", timeout=30).text
    for needle in ["competId", "rencId", "api/", "oddsv2", "getMatches", "wimbledon"]:
        print(needle, page.lower().count(needle.lower()))


if __name__ == "__main__":
    main()
