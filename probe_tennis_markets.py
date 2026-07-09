"""Inspect Coteur tennis market outcome structure."""

import json

from coteur_client import CoteurClient


def show_market(client: CoteurClient, renc_id: int, typename: str, special: str = "") -> None:
    data = client.get_market_odds(renc_id, typename, special)
    print(f"\n=== {typename} {special!r} ===")
    print("bestfr", data.get("bestfr"))
    for value in data.get("values", [])[:3]:
        print(" book", value.get("bookId"), value.get("current"))


def main() -> None:
    client = CoteurClient()
    renc_id = 1596959
    for typename, special in [
        ("12", ""),
        ("OU", "3-5"),
        ("OUJ", "35-5"),
        ("HT", ""),
        ("HT1", ""),
        ("HT2", ""),
        ("HTFT2", ""),
        ("BTTS", ""),
        ("EXACT", ""),
    ]:
        show_market(client, renc_id, typename, special)


if __name__ == "__main__":
    main()
